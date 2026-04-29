<template>
  <!-- Connection overlay -->
  <div v-if="!connected" class="connecting-overlay">
    <div class="spinner"></div>
    <!-- Startup error overlay: shown when edmd.py fails before WebSocket is ready -->
    <div v-if="startupError" class="startup-overlay">
      <div class="startup-card">
        <div class="startup-icon">⚠</div>
        <div class="startup-title">{{ startupError.title }}</div>
        <pre class="startup-message">{{ startupError.message }}</pre>
        <div v-if="startupError.action" class="startup-action">{{ startupError.action }}</div>
        <div class="startup-btns">
          <button v-if="startupError.config_path"
                  class="startup-btn primary"
                  @click="openInEditor(startupError.config_path)">
            Open config.toml
          </button>
          <button class="startup-btn" @click="openLog">View diagnostic log</button>
          <button class="startup-btn" @click="showPrefs = true; startupError = null">
            Open Preferences
          </button>
        </div>
      </div>
    </div>
    <div v-else-if="!connected" class="msg">{{ connectMsg }}</div>
  </div>

  <template v-else>
    <!-- Custom titlebar at top (frameless window) -->
    <TitleBar
      :program="program"
      :version="version"
      :update-notice="updateNotice"
      @reset="send({ cmd: 'reset_session' })"
      @alerts="send({ cmd: 'clear_alerts' })"
      @reports="showReports = true"
      @settings="showPrefs = true"
      @report="onTitlebarReport"
    />

    <!-- Dashboard -->
    <div class="dashboard">
      <div class="col col-left">
        <CareerBlock        :data="state.career"        />
        <SessionStatsBlock  :data="state.session_stats" />
        <ColonisationBlock  :data="state.colonisation"  />
      </div>
      <div class="col col-centre">
        <CommanderBlock :data="state.commander" @send="sendAndRoute" />
        <AlertsBlock    :data="state.alerts"    />
        <MissionsBlock  :data="state.missions"  />
        <CargoBlock     :data="state.cargo"     @send="sendAndRoute" />
      </div>
      <div class="col col-right">
        <CrewSlfBlock     :data="state.crew"        />
        <AssetsBlock      :data="state.assets"      />
        <EngineeringBlock :data="state.engineering" />
      </div>
    </div>

    <!-- Modals -->
    <PreferencesPanel v-if="showPrefs"
      ref="prefsPanel"
      @close="showPrefs = false"
      @send="sendAndRoute" />

    <ReportsPanel v-if="showReports"
      ref="reportsPanel"
      @close="showReports = false"
      @send="sendAndRoute" />
  </template>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';

import CommanderBlock    from './components/CommanderBlock.vue';
import AlertsBlock       from './components/AlertsBlock.vue';
import MissionsBlock     from './components/MissionsBlock.vue';
import CargoBlock        from './components/CargoBlock.vue';
import CrewSlfBlock      from './components/CrewSlfBlock.vue';
import AssetsBlock       from './components/AssetsBlock.vue';
import EngineeringBlock  from './components/EngineeringBlock.vue';
import CareerBlock       from './components/CareerBlock.vue';
import SessionStatsBlock from './components/SessionStatsBlock.vue';
import ColonisationBlock from './components/ColonisationBlock.vue';
import PreferencesPanel  from './components/PreferencesPanel.vue';
import ReportsPanel      from './components/ReportsPanel.vue';
import TitleBar          from './components/TitleBar.vue';

// ── UI state ──────────────────────────────────────────────────────────────────
const connected    = ref(false);
const connectMsg   = ref('Connecting to EDMD...');
const startupError = ref(null);
const updateNotice = ref('');
const showPrefs    = ref(false);
const showReports  = ref(false);
const version      = ref('');
const program      = ref('Elite Dangerous Monitor Daemon');
const prefsPanel   = ref(null);
const reportsPanel = ref(null);

const state = reactive({
  commander:    {},
  alerts:       { alerts: [] },
  missions:     { active_missions: [], stack_value: 0 },
  cargo:        { items: [], capacity: 0, used: 0 },
  crew:         {},
  assets:       {},
  engineering:  { raw: [], manufactured: [], encoded: [] },
  career:       {},
  session_stats:{},
  colonisation: { projects: [] },
});

// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws = null; let wsPort = null; let retries = 0;
const MAX_RETRIES = 10;

// Deep merge: replace nested objects by key so Vue reactivity fires on all levels.
// Object.assign only triggers reactivity for top-level keys; nested object references
// like state.commander._home would not trigger template re-renders.
function deepMerge(target, source) {
  for (const [k, v] of Object.entries(source)) {
    if (v !== null && typeof v === 'object' && !Array.isArray(v) &&
        k in target && typeof target[k] === 'object' && target[k] !== null) {
      deepMerge(target[k], v);
    } else {
      target[k] = v;
    }
  }
}

function applyMessage(msg) {
  const { event, data } = msg;

  if (event === 'initial_state') {
    // Extract version metadata before merging dashboard state
    if (data._meta?.version) {
      version.value = data._meta.version;
      const prog = data._meta?.program || 'Elite Dangerous Monitor Daemon';
      program.value = prog;
      document.title = `${prog} v${data._meta.version}`;
    }
    for (const [k, v] of Object.entries(data)) {
      if (k === '_meta') continue;
      if (k in state) deepMerge(state[k], v);
    }
    return;
  }

  if (event in state) { deepMerge(state[event], data); return; }
  if (event === 'update_notice') { updateNotice.value = `v${data.value} available`; return; }
  if (event === 'prefs_data') {
    prefsPanel.value?.applyPrefsData(data);
    if (data.ui_cfg?.Theme) applyTheme(data.ui_cfg.Theme);
    return;
  }
  if (event === 'report_data') { reportsPanel.value?.applyReport(data);  return; }
  if (event === 'log')         { console.log('[edmd]', data.line); }

  // Route search results back to the component that requested them
  if (msg.results !== undefined || msg.home !== undefined) {
    // This is a direct command response — route to any waiting callback
    for (const [key, cb] of _pendingCallbacks.entries()) {
      _pendingCallbacks.delete(key);
      cb(msg);
      return;
    }
  }
}

function send(cmd) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(cmd));
}
function onTitlebarReport(displayName) {
  // Map TitleBar display name to REPORT_REGISTRY key and request via WebSocket
  const nameToKey = {
    'Career Overview':    'career',
    'Bounty Breakdown':   'bounty',
    'Session History':    'sessions',
    'Hunting Grounds':    'grounds',
    "NPC Rogues' Gallery":'rogues',
    'Exploration':        'exploration',
    'Exobiology':         'exobiology',
    'PowerPlay':          'powerplay',
  };
  const key = nameToKey[displayName];
  if (!key) { console.warn('Unknown report:', displayName); return; }
  sendAndRoute({ cmd: 'run_report', report: key });
  showReports.value = true;
}

function openInEditor(filePath) {
  if (window.edmd?.openExternal && filePath)
    window.edmd.openExternal('file:///' + filePath.replace(/\\/g, '/'));
}
function openLog() { window.edmd?.openLog?.(); }

function sendAndRoute(cmd) {
  // Commands with _callback expect a response routed back
  const cb = cmd._callback;
  if (cb) {
    const { _callback, ...cleanCmd } = cmd;
    // For Spansh search commands, we need to send and get response
    // We do this by tracking pending callbacks
    _pendingCallbacks.set(cleanCmd.cmd + ':' + (cleanCmd.query || ''), cb);
    send(cleanCmd);
    return;
  }
  send(cmd);
}

// Map of pending Spansh search callbacks
const _pendingCallbacks = new Map();

// ── Theme palettes ─────────────────────────────────────────────────────────────
// Mirrors CSS variable values from themes/*.css; applied to :root at runtime.
const THEMES = {
  'default':        { '--accent':'#e07b20','--accent-bright':'#f09030','--accent-dim':'#9e5614','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(224,123,32,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-dark':   { '--accent':'#e07b20','--accent-bright':'#f09030','--accent-dim':'#9e5614','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(224,123,32,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-green':  { '--accent':'#00aa44','--accent-bright':'#00cc55','--accent-dim':'#007730','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(0,170,68,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-blue':   { '--accent':'#3d8fd4','--accent-bright':'#5aaef0','--accent-dim':'#2a6396','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(61,143,212,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-purple': { '--accent':'#9b59b6','--accent-bright':'#b07cc8','--accent-dim':'#6c3d80','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(155,89,182,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-red':    { '--accent':'#cc3333','--accent-bright':'#e04444','--accent-dim':'#8f2323','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(204,51,51,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
  'default-yellow': { '--accent':'#d4a017','--accent-bright':'#e8b820','--accent-dim':'#957010','--bg':'#0d0f12','--bg-panel':'#161a1f','--bg-header':'#1c2128','--bg-hover':'rgba(212,160,23,0.15)','--border':'#2a3040','--text':'#d8dce5','--text-dim':'#606878','--health-good':'#57e389','--health-warn':'#f8e45c','--health-crit':'#e05c5c' },
};

function applyTheme(name) {
  const palette = THEMES[name] || THEMES['default'];
  const root = document.documentElement;
  for (const [k, v] of Object.entries(palette)) root.style.setProperty(k, v);
}

async function connect() {
  if (!wsPort) {
    try { wsPort = await window.edmd?.getWsPort(); } catch (_) {}
    if (!wsPort) {
      const p = new URLSearchParams(window.location.search);
      wsPort = parseInt(p.get('wsPort') || '0', 10);
    }
  }
  if (!wsPort) {
    const _p = new URLSearchParams(window.location.search);
    const _raw = _p.get('startupError');
    if (_raw) {
      try { startupError.value = JSON.parse(decodeURIComponent(_raw)); }
      catch (_) { startupError.value = { title: 'Startup failed', message: _raw, action: '', config_path: '' }; }
    } else {
      startupError.value = { title: 'EDMD did not start', message: 'No WebSocket port was provided.', action: 'Check the diagnostic log for details.', config_path: '' };
    }
    return;
  }

  ws = new WebSocket(`ws://127.0.0.1:${wsPort}`);
  ws.onopen    = () => { connected.value = true; retries = 0; };
  ws.onmessage = ({ data: raw }) => {
    try { applyMessage(JSON.parse(raw)); } catch (e) { console.warn(e); }
  };
  ws.onclose   = () => {
    connected.value = false; retries++;
    if (retries <= MAX_RETRIES) {
      connectMsg.value = `Reconnecting… (${retries}/${MAX_RETRIES})`;
      setTimeout(connect, 1500);
    } else { connectMsg.value = 'Connection lost. Restart the application.'; }
  };
  ws.onerror = () => { connectMsg.value = `Waiting for EDMD on port ${wsPort}…`; };
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
function onKey(e) {
  // Never intercept keystrokes when the user is typing in an input or textarea
  const tag = document.activeElement?.tagName;
  const inInput = tag === 'INPUT' || tag === 'TEXTAREA';

  if (e.key === 'Escape') {
    if (inInput) { document.activeElement.blur(); return; }
    showPrefs.value = false;
    showReports.value = false;
    return;
  }

  // All remaining shortcuts are disabled when focus is in a text field
  if (inInput) return;

  // Ctrl-key shortcuts only — no single-key shortcuts (they break text input)
  if (e.ctrlKey) {
    if (e.key === 'r') { e.preventDefault(); send({ cmd: 'reset_session' }); }
    if (e.key === 'l') { e.preventDefault(); send({ cmd: 'clear_alerts'  }); }
    if (e.key === 'o') { e.preventDefault(); showPrefs.value = !showPrefs.value; }
  }
}

onMounted(() => {
  connect();
  window.addEventListener('keydown', onKey);
  window.addEventListener('edmd-error', () => {
    if (window.__edmdError) startupError.value = window.__edmdError;
  });
});
onUnmounted(() => { window.removeEventListener('keydown', onKey); if (ws) ws.close(); });
</script>

<style scoped>
/* Toolbar sits at the bottom, matching TUI convention */
.dashboard {
  display:               grid;
  grid-template-columns: 34% 34% 32%;
  height:                calc(100vh - 32px);   /* subtract TitleBar height */
  gap:                   var(--panel-gap);
  padding:               var(--panel-gap) var(--panel-gap) 0;
  background:            var(--bg);
}

.col {
  display:        flex;
  flex-direction: column;
  gap:            var(--panel-gap);
  min-height:     0;
  overflow:       hidden;
}

.col-left   > :nth-child(1) { flex: 25; }
.col-left   > :nth-child(2) { flex: 45; }
.col-left   > :nth-child(3) { flex: 30; }
.col-centre > :nth-child(1) { flex: 35; }
.col-centre > :nth-child(2) { flex: 12; }
.col-centre > :nth-child(3) { flex: 28; }
.col-centre > :nth-child(4) { flex: 25; }
.col-right  > :nth-child(1) { flex: 12; }   /* Crew: minimal - just the 4 data rows */
.col-right  > :nth-child(2) { flex: 44; }   /* Assets */
.col-right  > :nth-child(3) { flex: 44; }   /* Engineering: extra space from Crew */

/* Bottom toolbar */
/* (toolbar removed — now in TitleBar.vue) */

/* ── Startup error overlay ─────────────────────────────────────────────────── */
.startup-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: var(--bg); display: flex; align-items: center; justify-content: center;
}
.startup-card {
  background: var(--bg-panel); border: 1px solid var(--health-crit);
  border-radius: 4px; padding: 32px 40px; max-width: 560px; width: 90%;
  display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center;
}
.startup-icon    { font-size: 36px; color: var(--health-crit); line-height: 1; }
.startup-title   { font-size: 16px; font-weight: bold; color: var(--accent); }
.startup-message {
  font-family: inherit; font-size: 12px; color: var(--text); white-space: pre-wrap;
  text-align: left; width: 100%; background: var(--bg); border: 1px solid var(--border);
  padding: 10px 14px; border-radius: 3px; margin: 0; max-height: 200px; overflow-y: auto;
}
.startup-action  { font-size: 12px; color: var(--text-dim); text-align: left; width: 100%; }
.startup-btns    { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 4px; }
.startup-btn {
  padding: 6px 18px; border-radius: 3px; font-family: inherit; font-size: 12px;
  cursor: pointer; background: var(--bg); border: 1px solid var(--border); color: var(--text);
}
.startup-btn:hover         { border-color: var(--accent); color: var(--accent); }
.startup-btn.primary       { background: var(--accent); color: #000; border-color: var(--accent-bright); }
.startup-btn.primary:hover { background: var(--accent-bright); }
</style>
