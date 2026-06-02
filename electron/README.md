# EDMD Electron GUI

Cross-platform graphical frontend for EDMD. Wraps `edmd.py` as a subprocess
and renders the live dashboard in an Electron window via a local WebSocket bridge.

The Python backend is completely unchanged — all existing modes (`terminal`,
`textual`) continue to work exactly as before.

---
## Notice
Support for Electron GUI was added by the original developer but hasn't been tested by the current developer. Your mileage may vary, I welcome recommendations for improvements though!

## Prerequisites

- **Python 3.11+** with EDMD dependencies installed (`pip install -r requirements.txt`)
- **`websockets>=12.0`** for the Python bridge: `pip install 'websockets>=12.0'`
- **Node.js 20+** and npm

---

## First-time setup

```bash
cd electron
npm install
```

---

## Running in development

**One command from the `electron/` directory:**

```bash
EDMD_ARGS="-p YourProfile" npm run dev
```

This starts the Vite dev server and Electron together via `concurrently`, waiting
for Vite to be ready before opening the window. Replace `YourProfile` with your
config profile name (or omit `EDMD_ARGS` entirely if your JournalFolder is in
the default config).

Examples:

```bash
# Profile named EDP1
EDMD_ARGS="-p EDP1" npm run dev

# Profile with trace logging
EDMD_ARGS="-p EDP1 --trace" npm run dev

# Default config (JournalFolder set in config.toml directly)
npm run dev
```

> ⚠️ **Do not** run `npx electron .` directly in dev mode without first starting
> the Vite server. The window will show an error because `localhost:5173` isn't up.
> Always use `npm run dev`.

---

## Debugging: running edmd.py separately

For Python-side debugging, you can run the backend manually and tell Electron
not to spawn its own copy:

```bash
# Terminal 1 — Python backend
python3 edmd.py -p EDP1 --mode electron

# Terminal 2 — Vite dev server
cd electron && npm run dev:renderer

# Terminal 3 — Electron (EDMD_EXTERNAL=1 skips spawning edmd.py)
cd electron && EDMD_EXTERNAL=1 EDMD_DEV=1 npx electron .
```

---

## Environment variables

| Variable | Purpose |
|---|---|
| `EDMD_DEV=1` | Load renderer from Vite dev server (localhost:5173) |
| `EDMD_ARGS="-p X"` | Extra args passed to `edmd.py` — profile, `--trace`, etc. |
| `EDMD_EXTERNAL=1` | Don't spawn `edmd.py` — connect to an already-running instance |
| `EDMD_PY=/path` | Explicit path to `edmd.py` (auto-detected from repo layout) |
| `EDMD_PYTHON=/path` | Python interpreter (default: `python3`) |
| `EDMD_DATA_DIR=/path` | EDMD data directory (default: `~/.local/share/EDMD`) |

---

## Building distribution artifacts

```bash
# Build renderer first, then package
cd electron

npm run build:linux   # AppImage + .deb  (run on Linux)
npm run build:win     # NSIS .exe installer (run on Windows)
npm run build:mac     # .dmg (run on macOS)
```

Built files appear in `electron/dist/`. The GitHub Actions release workflow
builds all platforms automatically when you publish a release on GitHub.

---

## Architecture

```
EDMD AppImage / .exe / electron .
    │
    ├── Spawns: python3 edmd.py --mode electron [-p Profile ...]
    │       │
    │       ├── Runs journal parsing, components, Discord, etc. as normal
    │       └── Starts WebSocket server on 127.0.0.1:{random port}
    │           Writes port to ~/.local/share/EDMD/electron.port
    │
    └── Reads electron.port → loads renderer with ws://127.0.0.1:{port}
        └── Vue app connects, receives live state pushes, sends commands back
```

All existing EDMD modes are completely unaffected.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open Preferences |
| `R` | Open Reports |
| `Ctrl+R` | Reset session |
| `Ctrl+L` | Clear alerts |
| `Escape` | Close modal |
