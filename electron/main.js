/**
 * electron/main.js — Electron main process
 *
 * Responsibilities:
 *   1. Load Electron-side config (edmd-electron.json in userData dir)
 *   2. Optionally spawn edmd.py with --mode electron as a child process
 *   3. Wait for EDMD_DATA_DIR/electron.port to appear
 *   4. Open BrowserWindow and load the renderer with wsPort in URL
 *   5. Clean up on exit
 *
 * Electron-side config  (app.getPath('userData')/edmd-electron.json)
 * ─────────────────────
 *   edmdPath    Path to edmd.py (required on Windows; auto-detected on Linux/macOS)
 *   pythonPath  Python interpreter path (optional; auto-detected if absent)
 *   profile     EDMD profile name — passed as -p PROFILE (optional)
 *   extraArgs   Additional CLI args string (optional)
 *
 * Environment variable overrides (for developers)
 * ─────────────────────────────────────────────────
 *   EDMD_DEV      = '1'   Load renderer from Vite dev server (localhost:5173)
 *   EDMD_PY       = path  Explicit path to edmd.py (overrides config + search)
 *   EDMD_PYTHON   = path  Python interpreter (overrides config + auto-detect)
 *   EDMD_DATA_DIR = path  EDMD data directory (default: platform-appropriate)
 *   EDMD_ARGS     = str   Extra CLI args (appended after config extraArgs)
 *   EDMD_EXTERNAL = '1'   Skip spawning edmd.py; connect to already-running instance
 *
 * Diagnostics
 * ───────────
 *   A plain-text log is written to EDMD_DATA_DIR/electron-launcher.log.
 *   Check this file first when the app fails to connect.
 */

'use strict';

const { app, BrowserWindow, ipcMain, shell, dialog, Menu } = require('electron');
const path = require('path');
const fs   = require('fs');
const cp   = require('child_process');
const os   = require('os');

// ── Log file ──────────────────────────────────────────────────────────────────
// Written early so every launch attempt is captured.

// DATA_DIR may not exist yet — resolve it before app.whenReady so the log
// starts immediately.
const DATA_DIR = process.env.EDMD_DATA_DIR
  || (process.platform === 'win32'
      ? path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'EDMD')
      : process.platform === 'darwin'
        ? path.join(os.homedir(), 'Library', 'Application Support', 'EDMD')
        : path.join(os.homedir(), '.local', 'share', 'EDMD'));

const LOG_FILE  = path.join(DATA_DIR, 'electron-launcher.log');
const PORT_FILE = path.join(DATA_DIR, 'electron.port');

let logStream = null;
function initLog() {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    // Keep log under 50 KB — truncate on open if over
    try { if (fs.statSync(LOG_FILE).size > 50_000) fs.writeFileSync(LOG_FILE, ''); } catch (_) {}
    logStream = fs.createWriteStream(LOG_FILE, { flags: 'a' });
  } catch (e) {
    console.error('[EDMD] Could not open log file:', e.message);
  }
}

function log(...parts) {
  const ts  = new Date().toISOString();
  const msg = `[${ts}] ${parts.join(' ')}\n`;
  process.stdout.write(msg);
  try { logStream?.write(msg); } catch (_) {}
}

initLog();
log('=== EDMD Electron launcher starting', app.getVersion(), '===');
log('Platform:', process.platform, process.arch);
log('DATA_DIR:', DATA_DIR);
log('LOG_FILE:', LOG_FILE);

// ── Electron-side config ──────────────────────────────────────────────────────

const CONFIG_FILE = path.join(app.getPath('userData'), 'edmd-electron.json');

function loadConfig() {
  try {
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    log('Config loaded from', CONFIG_FILE);
    return cfg;
  } catch (_) {
    log('No config file found — using defaults');
    return {};
  }
}

function saveConfig(data) {
  fs.mkdirSync(path.dirname(CONFIG_FILE), { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(data, null, 2), 'utf8');
  log('Config saved to', CONFIG_FILE);
}

// ── Constants ─────────────────────────────────────────────────────────────────

const IS_DEV      = process.env.EDMD_DEV === '1' || !app.isPackaged;
const IS_EXTERNAL = process.env.EDMD_EXTERNAL === '1';

const RENDERER = IS_DEV
  ? 'http://localhost:5173'
  : `file://${path.join(__dirname, 'renderer/dist/index.html')}`;

const PORT_WAIT_MS = 30_000;   // 30 s — generous for slow Windows startup
const PORT_POLL_MS = 200;

log('IS_DEV:', IS_DEV, '  IS_EXTERNAL:', IS_EXTERNAL);
log('RENDERER:', RENDERER);

// ── Python / edmd.py discovery ────────────────────────────────────────────────

function findEdmdPy(cfg) {
  if (process.env.EDMD_PY) {
    log('EDMD_PY env override:', process.env.EDMD_PY);
    return process.env.EDMD_PY;
  }
  if (cfg.edmdPath) {
    const exists = fs.existsSync(cfg.edmdPath);
    log(`Config edmdPath: ${cfg.edmdPath}  (exists: ${exists})`);
    if (exists) return cfg.edmdPath;
  }
  const candidates = [
    // 1. Bundled inside the packaged app (extraResources/edmd-src/) — primary
    //    path for installed users on all platforms.
    path.join(process.resourcesPath, 'edmd-src', 'edmd.py'),
    // 2. Dev: running Electron directly from the repo (electron/ subdirectory)
    path.join(__dirname, '..', 'edmd.py'),
    // 3. Fallback: common user-installed locations
    path.join(os.homedir(), '.local', 'share', 'EDMD', 'edmd.py'),
    path.join(os.homedir(), '.local', 'share', 'EDMD', 'src', 'edmd.py'),
    path.join(os.homedir(), 'EDMD', 'edmd.py'),
    path.join(os.homedir(), 'Documents', 'EDMD', 'edmd.py'),
    path.join(os.homedir(), 'Desktop', 'EDMD', 'edmd.py'),
    path.join('C:\\', 'EDMD', 'edmd.py'),
    path.join(os.homedir(), 'AppData', 'Local', 'EDMD', 'edmd.py'),
  ];
  for (const c of candidates) {
    const exists = fs.existsSync(c);
    log(`  check: ${c}  →  ${exists ? 'FOUND' : 'missing'}`);
    if (exists) return c;
  }
  log('edmd.py NOT FOUND in any candidate location');
  return null;
}

function buildArgv(cfg, edmdPy) {
  // -u: force unbuffered stdout/stderr so pipe data events fire immediately
  // on Windows where PYTHONUNBUFFERED alone is sometimes insufficient
  const args = ['-u', edmdPy, '--mode', 'electron'];
  const profile = cfg.profile || '';
  if (profile) { args.push('-p', profile); log('Profile:', profile); }
  const cfgExtra = (cfg.extraArgs || '').trim();
  const envExtra = (process.env.EDMD_ARGS || '').trim();
  const combined = [cfgExtra, envExtra].filter(Boolean).join(' ');
  if (combined) args.push(...combined.split(/\s+/));
  return args;
}

// ── subprocess ────────────────────────────────────────────────────────────────

let edmdProc   = null;
let wsPort     = null;
let mainWindow = null;
let spawnError = null;

async function spawnEdmd(cfg) {
  if (IS_EXTERNAL) { log('EDMD_EXTERNAL=1 — skipping spawn'); return; }

  const edmdPy = findEdmdPy(cfg);
  if (!edmdPy) {
    spawnError = {
      type: 'not_found',
      message:
        `Cannot find edmd.py.\n\n` +
        `Open Settings → Preferences → Setup and set the path to your EDMD installation.\n\n` +
        `Diagnostic log: ${LOG_FILE}`,
    };
    log('ERROR:', spawnError.message);
    return;
  }

  const argv = buildArgv(cfg, edmdPy);

  // Python interpreter: env override → config → auto candidates
  const basePy = process.env.EDMD_PYTHON || cfg.pythonPath || null;
  // Bundled Python (Windows installer): always try this first.
  // It lives at resources/python/python.exe alongside edmd-src/.
  const bundledPy = path.join(process.resourcesPath, 'python', 'python.exe');
  log('process.resourcesPath:', process.resourcesPath);
  log('bundledPy check:', bundledPy, '  exists:', fs.existsSync(bundledPy));
  const hasBundled = process.platform === 'win32' && fs.existsSync(bundledPy);

  const candidates = basePy
    ? [basePy]
    : process.platform === 'win32'
      ? (hasBundled ? [bundledPy] : ['python', 'py'])
      : ['python3', 'python'];

  log('Python candidates:', candidates.join(', '));

  try { fs.unlinkSync(PORT_FILE); } catch (_) {}
  // Clear any stale error file from a previous failed launch
  const ERROR_FILE = path.join(DATA_DIR, 'electron-error.json');
  try { fs.unlinkSync(ERROR_FILE); } catch (_) {}

  let launched = false;
  for (const interpreter of candidates) {
    log(`Trying: ${interpreter} ${argv.join(' ')}`);
    // Redirect Python stdout/stderr directly into the log file via fd.
    // Node.js pipe events are unreliable on Windows for windowsHide subprocesses.
    let logFd = -1;
    try { logFd = fs.openSync(LOG_FILE, 'a'); } catch (_) {}

    const proc = cp.spawn(interpreter, argv, {
      stdio:       ['ignore', logFd >= 0 ? logFd : 'pipe', logFd >= 0 ? logFd : 'pipe'],
      env:         {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      windowsHide: true,
    });

    // Probe: if the interpreter binary doesn't exist, the error event fires
    // quickly with ENOENT. Give it 500 ms to surface.
    const probeOk = await new Promise(resolve => {
      let done = false;
      const finish = (ok) => { if (!done) { done = true; resolve(ok); } };
      proc.on('error', err => {
        log(`Spawn error (${interpreter}): ${err.code} — ${err.message}`);
        if (logFd >= 0) try { fs.closeSync(logFd); } catch (_) {}
        finish(false);
      });
      setTimeout(() => finish(true), 500);
    });

    if (!probeOk) {
      try { proc.kill(); } catch (_) {}
      continue;
    }

    // Interpreter found — Python writes directly to log fd; just handle exit
    edmdProc = proc;
    launched = true;

    proc.on('exit', (code, sig) => {
      if (logFd >= 0) try { fs.closeSync(logFd); } catch (_) {}
      log(`edmd.py exited — code=${code} sig=${sig}`);
      edmdProc = null;

      if (code === 0 && wsPort) {
        // Clean exit while running = Python restarted itself (save_prefs restart).
        // os.execv on Windows exits the original process and spawns a new one with
        // a new PID that main.js doesn't track. Respawn from our side instead.
        log('Clean exit while running — respawning edmd.py in 800ms...');
        wsPort = null;
        try { fs.unlinkSync(PORT_FILE); } catch (_) {}
        setTimeout(async () => {
          const cfg = loadConfig();
          await spawnEdmd(cfg);
          if (!spawnError) {
            try {
              wsPort = await waitForPort();
              log('Respawn ready on port', wsPort);
              if (mainWindow) {
                const u = new URL(RENDERER);
                u.searchParams.set('wsPort', String(wsPort));
                mainWindow.loadURL(u.toString());
              }
            } catch (err) {
              log('Respawn timeout:', err.message);
              spawnError = { type: 'timeout', title: 'Restart failed', message: err.message, action: `Check the diagnostic log:\n${LOG_FILE}`, config_path: '' };
              if (mainWindow) {
                mainWindow.webContents.executeJavaScript(
                  `window.__edmdError = ${JSON.stringify(spawnError)};` +
                  `window.dispatchEvent(new Event('edmd-error'));`
                ).catch(() => {});
              }
            }
          }
        }, 800);
        return;
      }

      // Non-zero exit or died before port was ready — surface the error
      if (mainWindow) {
        let errObj;
        const ERROR_FILE = path.join(DATA_DIR, 'electron-error.json');
        try {
          errObj = JSON.parse(fs.readFileSync(ERROR_FILE, 'utf8'));
          log('Structured error from Python:', errObj.type);
        } catch (_) {
          errObj = {
            type:    'crash',
            title:   'EDMD exited unexpectedly',
            message: `edmd.py exited with code ${code}.\n\nCheck the diagnostic log for details:\n${LOG_FILE}`,
            action:  'View the log file to see the Python error.',
          };
        }
        mainWindow.webContents.executeJavaScript(
          `window.__edmdError = ${JSON.stringify(errObj)};` +
          `window.dispatchEvent(new Event('edmd-error'));`
        ).catch(() => {});
      }
    });

    log(`Spawned ${interpreter} (pid ${proc.pid})`);
    break;
  }

  if (!launched) {
    spawnError = {
      type: 'no_python',
      message:
        `No Python interpreter found.\n\n` +
        `Install Python 3.11+ and ensure it is on your PATH,\n` +
        `or set the interpreter path in Settings → Preferences → Setup.\n\n` +
        `Diagnostic log: ${LOG_FILE}`,
    };
    log('ERROR:', spawnError.message);
  }
}

function waitForPort() {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + PORT_WAIT_MS;
    const check = () => {
      try {
        const port = parseInt(fs.readFileSync(PORT_FILE, 'utf8').trim(), 10);
        if (port > 0) { log('Port file read — port:', port); return resolve(port); }
      } catch (_) {}
      if (Date.now() > deadline) {
        return reject(new Error(
          `edmd.py did not become ready within ${PORT_WAIT_MS / 1000}s.\n\n` +
          `Check the diagnostic log:\n${LOG_FILE}`
        ));
      }
      setTimeout(check, PORT_POLL_MS);
    };
    check();
  });
}

// ── Error page (dev mode only) ────────────────────────────────────────────────

function devServerErrorHtml() {
  return `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  body { background:#0d0d0d; color:#d4d4d4; font-family:monospace;
         display:flex; flex-direction:column; align-items:center;
         justify-content:center; height:100vh; margin:0; gap:16px; }
  h2   { color:#e07b20; margin:0; }
  pre  { background:#141414; border:1px solid #2a2a2a; padding:12px 20px;
         border-radius:3px; font-size:13px; line-height:1.6; }
</style></head><body>
  <h2>Vite dev server not running</h2>
  <pre>Run from the electron/ directory:\n\n  npm run dev\n\nDo not run 'npx electron .' directly in dev mode.</pre>
  <script>setTimeout(() => location.reload(), 3000);</script>
</body></html>`;
}

// ── Window ────────────────────────────────────────────────────────────────────

async function createWindow() {
  mainWindow = new BrowserWindow({
    width:          1600,
    height:          900,
    minWidth:        1024,
    minHeight:        600,
    backgroundColor: '#0d0d0d',
    autoHideMenuBar: true,
    frame:           false,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          false,
    },
  });

  const url = new URL(RENDERER);
  url.searchParams.set('wsPort', wsPort || '0');
  if (spawnError) {
    url.searchParams.set('startupError', encodeURIComponent(JSON.stringify(spawnError)));
  }
  log('Loading URL:', url.toString().substring(0, 120));
  mainWindow.loadURL(url.toString());

  if (IS_DEV) {
    mainWindow.webContents.on('did-fail-load', (_evt, _code, desc) => {
      if (desc === 'ERR_CONNECTION_REFUSED') {
        mainWindow.webContents.loadURL(
          'data:text/html,' + encodeURIComponent(devServerErrorHtml())
        );
      }
    });
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ── IPC ───────────────────────────────────────────────────────────────────────

ipcMain.handle('get-ws-port',   () => wsPort);
ipcMain.handle('get-version',   () => app.getVersion());
ipcMain.handle('get-log-path',  () => LOG_FILE);
ipcMain.handle('win-minimize',  () => { mainWindow?.minimize(); });
ipcMain.handle('win-maximize',  () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle('win-fullscreen',() => {
  mainWindow?.setFullScreen(!mainWindow.isFullScreen());
});
ipcMain.handle('win-close',     () => { mainWindow?.close(); });
ipcMain.handle('win-is-max',    () => mainWindow?.isMaximized() ?? false);
ipcMain.handle('open-external', (_, url) => { shell.openExternal(url); });

ipcMain.handle('get-edmd-config',  () => loadConfig());
ipcMain.handle('save-edmd-config', (_, data) => { saveConfig(data); return { ok: true }; });

ipcMain.handle('browse-file', async (_, opts = {}) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    title:      opts.title || 'Select file',
    filters:    opts.filters || [{ name: 'Python scripts', extensions: ['py'] }],
    properties: ['openFile'],
    defaultPath: opts.defaultPath || os.homedir(),
  });
  return result.canceled ? null : result.filePaths[0];
});

// Open the log file in the system's default text viewer
ipcMain.handle('open-log', () => { shell.openPath(LOG_FILE); });

// ── Menu ──────────────────────────────────────────────────────────────────────

function buildMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        { label: 'Quit EDMD', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() },
      ],
    },
    ...(IS_DEV ? [{
      label: 'Dev',
      submenu: [
        { label: 'Reload',   accelerator: 'CmdOrCtrl+R',       click: () => mainWindow?.webContents.reload() },
        { label: 'DevTools', accelerator: 'CmdOrCtrl+Shift+I', click: () => mainWindow?.webContents.toggleDevTools() },
      ],
    }] : []),
  ];
  return Menu.buildFromTemplate(template);
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  const cfg = loadConfig();
  await spawnEdmd(cfg);

  if (!spawnError) {
    try {
      wsPort = await waitForPort();
      log('Bridge ready on port', wsPort);
    } catch (err) {
      log('ERROR:', err.message);
      // Try to read structured error from Python before falling back to generic timeout
      const ERROR_FILE = path.join(DATA_DIR, 'electron-error.json');
      try {
        const errJson = JSON.parse(fs.readFileSync(ERROR_FILE, 'utf8'));
        log('Structured error from Python:', errJson.type);
        spawnError = errJson;
      } catch (_) {
        spawnError = {
          type:    'timeout',
          title:   'EDMD did not start',
          message: err.message,
          action:  `Check the diagnostic log:\n${LOG_FILE}`,
        };
      }
      wsPort = 0;
    }
  }

  Menu.setApplicationMenu(buildMenu());
  await createWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on('window-all-closed', () => {
  if (edmdProc) edmdProc.kill('SIGTERM');
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  log('App quitting');
  if (edmdProc) edmdProc.kill('SIGTERM');
  try { fs.unlinkSync(PORT_FILE); } catch (_) {}
  logStream?.end();
});
