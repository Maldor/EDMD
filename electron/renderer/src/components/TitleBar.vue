<template>
  <!-- Full bar is draggable; only .no-drag children capture mouse events -->
  <div class="titlebar" @dblclick="onDblClick">

    <!-- LEFT: menu buttons matching GTK4 menu bar order -->
    <div class="tb-left no-drag">
      <div class="tb-menu-group">
        <!-- File -->
        <div class="tb-menu-wrap" ref="fileRef">
          <button class="tb-menu-btn" @click="toggleMenu('file')">File</button>
          <div v-if="openMenu === 'file'" class="tb-menu-popup">
            <button class="tb-menu-item" @click="doClose">✕  Exit</button>
          </div>
        </div>
        <!-- View -->
        <div class="tb-menu-wrap" ref="viewRef">
          <button class="tb-menu-btn" @click="toggleMenu('view')">View</button>
          <div v-if="openMenu === 'view'" class="tb-menu-popup">
            <button class="tb-menu-item" @click="doFullscreen">⛶  Full Screen</button>
          </div>
        </div>
        <!-- Settings -->
        <div class="tb-menu-wrap" ref="settingsRef">
          <button class="tb-menu-btn" @click="toggleMenu('settings')">Settings</button>
          <div v-if="openMenu === 'settings'" class="tb-menu-popup">
            <button class="tb-menu-item" @click="emit('settings'); closeMenu()">⚙  Preferences</button>
          </div>
        </div>
        <!-- Reports -->
        <div class="tb-menu-wrap" ref="reportsRef">
          <button class="tb-menu-btn" @click="toggleMenu('reports')">Reports</button>
          <div v-if="openMenu === 'reports'" class="tb-menu-popup">
            <button v-for="r in reports" :key="r" class="tb-menu-item"
                    @click="emit('report', r); closeMenu()">{{ r }}</button>
          </div>
        </div>
        <!-- Help -->
        <div class="tb-menu-wrap" ref="helpRef">
          <button class="tb-menu-btn" @click="toggleMenu('help')">Help</button>
          <div v-if="openMenu === 'help'" class="tb-menu-popup">
            <button class="tb-menu-item" @click="openUrl('https://github.com/maldor/EDMD/releases/latest'); closeMenu()">📄  Documentation</button>
            <button class="tb-menu-item" @click="openUrl('https://github.com/maldor/EDMD'); closeMenu()">🐙  GitHub</button>
            <div class="tb-menu-sep"></div>
            <button class="tb-menu-item" @click="closeMenu()">ℹ  About EDMD</button>
          </div>
        </div>
      </div>
    </div>

    <!-- CENTRE: program name + version, update notice when available -->
    <div class="tb-centre">
      <span class="tb-title" :class="{ 'tb-update': updateNotice }">
        {{ fullTitle }}
      </span>
    </div>

    <!-- RIGHT: window controls matching GTK4 order: fs | min | max | close -->
    <div class="tb-right no-drag">
      <button class="wc-btn" @click="doFullscreen" title="Toggle Fullscreen">⛶</button>
      <button class="wc-btn" @click="doMinimize"   title="Minimize">—</button>
      <button class="wc-btn" @click="doMaximize"   :title="isMax ? 'Restore' : 'Maximize'">
        {{ isMax ? '❐' : '□' }}
      </button>
      <button class="wc-btn close" @click="doClose" title="Close">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  program:      { type: String, default: 'EDMD' },
  version:      { type: String, default: '' },
  updateNotice: { type: String, default: '' },
});
const emit = defineEmits(['settings', 'report']);

const isMax    = ref(false);
const openMenu = ref('');

// Reports list — keys must match REPORT_REGISTRY display labels in core/reports.py
const reports = [
  'Career Overview', 'Bounty Breakdown', 'Session History', 'Hunting Grounds',
  "NPC Rogues' Gallery", 'Exploration', 'Exobiology', 'PowerPlay',
];

const fullTitle = computed(() => {
  const base = props.version ? `${props.program}  v${props.version}` : props.program;
  if (props.updateNotice) return `${base}  ·  ⬆ ${props.updateNotice}`;
  return base;
});

function toggleMenu(name) {
  openMenu.value = openMenu.value === name ? '' : name;
}
function closeMenu() { openMenu.value = ''; }

// Close menus when clicking outside
function onDocClick(e) {
  const isMenu = e.target.closest('.tb-menu-wrap');
  if (!isMenu) openMenu.value = '';
}

async function pollMax() {
  try { isMax.value = await window.edmd?.isMaximized() ?? false; } catch (_) {}
}
let pollTimer = null;

onMounted(() => {
  pollMax();
  pollTimer = setInterval(pollMax, 1500);
  document.addEventListener('click', onDocClick, true);
});
onUnmounted(() => {
  clearInterval(pollTimer);
  document.removeEventListener('click', onDocClick, true);
});

async function doMinimize()   { await window.edmd?.minimize?.(); }
async function doMaximize()   { await window.edmd?.maximize?.(); await pollMax(); }
async function doFullscreen() { await window.edmd?.fullscreen?.(); }
async function doClose()      { closeMenu(); await window.edmd?.close?.(); }
function onDblClick()         { doMaximize(); }

function openUrl(url) {
  closeMenu();
  if (window.edmd?.openExternal) window.edmd.openExternal(url);
  else window.open(url, '_blank');
}
</script>

<style scoped>
.titlebar {
  height:             30px;
  background:         var(--bg-header);
  border-bottom:      1px solid var(--border);
  display:            flex;
  align-items:        stretch;
  flex-shrink:        0;
  -webkit-app-region: drag;
  app-region:         drag;
  user-select:        none;
}
.no-drag {
  -webkit-app-region: no-drag;
  app-region:         no-drag;
}

/* LEFT — menu buttons */
.tb-left { display: flex; align-items: stretch; }
.tb-menu-group { display: flex; align-items: stretch; }
.tb-menu-wrap  { position: relative; display: flex; align-items: stretch; }
.tb-menu-btn   {
  background: none; border: none; border-bottom: 2px solid transparent;
  color: var(--text-dim); font-family: inherit; font-size: 11px;
  padding: 0 10px; cursor: pointer; white-space: nowrap;
  display: flex; align-items: center;
}
.tb-menu-btn:hover { color: var(--text); background: var(--bg-hover); }

/* Popups */
.tb-menu-popup {
  position:   absolute; top: 100%; left: 0; min-width: 160px;
  background: var(--bg-panel); border: 1px solid var(--border-accent);
  border-top: none; z-index: 200; box-shadow: 0 4px 12px rgba(0,0,0,.5);
}
.tb-menu-item {
  display: block; width: 100%; text-align: left;
  background: none; border: none; border-bottom: 1px solid var(--border);
  color: var(--text); font-family: inherit; font-size: 11px;
  padding: 5px 12px; cursor: pointer; white-space: nowrap;
}
.tb-menu-item:last-child { border-bottom: none; }
.tb-menu-item:hover { background: var(--bg-hover); color: var(--accent); }
.tb-menu-sep { height: 1px; background: var(--border); margin: 2px 0; }

/* CENTRE — title */
.tb-centre {
  flex: 1; display: flex; align-items: center; justify-content: center;
  pointer-events: none;  /* let drag-region work through centre */
}
.tb-title  { color: var(--accent); font-weight: bold; font-size: 12px; letter-spacing: 0.03em; }
.tb-update { color: var(--health-warn); }

/* RIGHT — window controls */
.tb-right { display: flex; align-items: stretch; }
.wc-btn {
  width: 28px; background: none; border: none;
  color: var(--text-dim); cursor: pointer;
  font-size: 13px; display: flex; align-items: center; justify-content: center;
}
.wc-btn:hover       { background: var(--bg-hover); color: var(--text); }
.wc-btn.close:hover { background: #c0392b; color: #fff; }
</style>
