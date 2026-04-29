<template>
  <div class="panel-overlay" @click.self="$emit('close')">
    <div class="prefs-window">
      <div class="prefs-header">
        <span>PREFERENCES</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="prefs-body">
        <div class="tab-bar">
          <button v-for="tab in tabs" :key="tab.id"
                  class="tab-btn" :class="{ active: activeTab === tab.id }"
                  @click="activeTab = tab.id">{{ tab.label }}</button>
        </div>

        <!-- Setup -->
        <div v-show="activeTab === 'setup'" class="tab-content">
          <div v-if="startupErrorMsg" class="startup-error">
            <div class="error-icon">⚠</div>
            <div style="flex:1">
              <pre class="error-text">{{ startupErrorMsg }}</pre>
              <button class="pref-btn" style="margin-top:8px"
                      @click="window.edmd?.openLog?.()">
                Open diagnostic log…
              </button>
            </div>
          </div>
          <div class="pref-section">EDMD INSTALLATION</div>
          <div class="pref-note">
            Point Electron to your EDMD Python installation.
            On Windows this must be set manually — on Linux/macOS it is usually auto-detected.
          </div>
          <PrefRow label="Path to edmd.py">
            <input v-model="edmdCfg.edmdPath" class="pref-input wide"
                   placeholder="Auto-detected (set manually on Windows)"
                   @input="markEdmdCfg('edmdPath', $event.target.value)" />
            <button class="pref-btn browse-btn" @click="browseEdmdPy">Browse…</button>
          </PrefRow>
          <PrefRow label="Python interpreter">
            <input v-model="edmdCfg.pythonPath" class="pref-input wide"
                   placeholder="Auto-detected  (pythonw / python3)"
                   @input="markEdmdCfg('pythonPath', $event.target.value)" />
            <button class="pref-btn browse-btn" @click="browsePython">Browse…</button>
          </PrefRow>

          <div class="pref-section">SESSION</div>
          <div class="pref-note">Profile selects a named configuration block from your config.toml.</div>
          <PrefRow label="Profile  (-p)">
            <input v-model="edmdCfg.profile" class="pref-input wide"
                   placeholder="Default profile (leave blank for [Settings])"
                   @input="markEdmdCfg('profile', $event.target.value)" />
          </PrefRow>
          <PrefRow label="Extra launch args">
            <input v-model="edmdCfg.extraArgs" class="pref-input wide"
                   placeholder="e.g. --trace  (optional)"
                   @input="markEdmdCfg('extraArgs', $event.target.value)" />
          </PrefRow>
          <div class="pref-note dim">
            Changes take effect on next launch. Use Save &amp; Close then restart EDMD.
          </div>
        </div>

        <!-- General -->
        <div v-show="activeTab === 'general'" class="tab-content">
          <div class="pref-section">SESSION</div>
          <PrefRow label="Journal Folder ⚠" restart>
            <input v-model="s.JournalFolder" class="pref-input widest" @input="mark('JournalFolder', $event.target.value, true)" />
          </PrefRow>
          <PrefRow label="Use UTC Timestamps" restart>
            <PrefSelect v-model="s.UseUTC" @change="mark('UseUTC', $event, true)" />
          </PrefRow>

          <div class="pref-section">DISPLAY</div>
          <PrefRow label="Truncate Names (chars)">
            <input v-model.number="s.TruncateNames" type="number" min="10" max="60"
                   class="pref-input narrow" @input="mark('TruncateNames', +$event.target.value)" />
          </PrefRow>
          <PrefRow label="Show Pirate Names">
            <PrefSelect v-model="s.PirateNames" @change="mark('PirateNames', $event)" />
          </PrefRow>
          <PrefRow label="Credit Value per Kill">
            <PrefSelect v-model="s.BountyValue" @change="mark('BountyValue', $event)" />
          </PrefRow>
          <PrefRow label="Victim Faction per Kill">
            <PrefSelect v-model="s.BountyFaction" @change="mark('BountyFaction', $event)" />
          </PrefRow>
          <PrefRow label="Extended Kill Stats">
            <PrefSelect v-model="s.ExtendedStats" @change="mark('ExtendedStats', $event)" />
          </PrefRow>

          <div class="pref-section">INACTIVITY ALERTS</div>
          <PrefRow label="Alert After N Minutes Without Kill">
            <input v-model.number="s.WarnNoKills" type="number" min="1" max="120"
                   class="pref-input narrow" @input="mark('WarnNoKills', +$event.target.value)" />
          </PrefRow>
          <PrefRow label="Alert When Kill Rate Below (kills/hr)">
            <input v-model.number="s.WarnKillRate" type="number" min="0" max="500"
                   class="pref-input narrow" @input="mark('WarnKillRate', +$event.target.value)" />
          </PrefRow>
          <PrefRow label="Alert Cooldown (minutes)">
            <input v-model.number="s.WarnCooldown" type="number" min="1" max="60"
                   class="pref-input narrow" @input="mark('WarnCooldown', +$event.target.value)" />
          </PrefRow>
        </div>

        <!-- Notifications -->
        <div v-show="activeTab === 'notifications'" class="tab-content">
          <div class="pref-section">LOG LEVELS  (0=off · 1=terminal · 2=+Discord · 3=+ping)</div>
          <PrefRow v-for="entry in notifEntries" :key="entry.key" :label="entry.label">
            <input v-model.number="nl[entry.key]" type="number" min="0" max="3"
                   class="pref-input narrow" @input="markNl(entry.key, +$event.target.value)" />
          </PrefRow>
        </div>

        <!-- Appearance -->
        <div v-show="activeTab === 'appearance'" class="tab-content">
          <div class="pref-section">THEME</div>
          <PrefRow label="Theme" restart>
            <select v-model="ui.Theme" class="pref-select"
                    @change="markUi('Theme', $event.target.value, true)">
              <option v-for="t in themes" :key="t" :value="t">{{ t }}</option>
            </select>
          </PrefRow>
        </div>

        <!-- Data & Integrations -->
        <div v-show="activeTab === 'data'" class="tab-content">
          <div class="pref-note">These settings require a restart to take effect.  ⚠ will confirm.</div>

          <!-- Frontier CAPI -->
          <div class="pref-section">Frontier CAPI</div>
          <div class="pref-note">
            Provides authoritative fleet data directly from Frontier.<br>
            Authenticates via your Frontier account in a browser window.<br>
            Tokens are stored locally and never sent anywhere else.
          </div>
          <PrefRow label="Status">
            <span class="capi-status" :class="{ connected: capiStatus.connected }">
              {{ capiStatus.state || 'Checking…' }}
            </span>
          </PrefRow>
          <PrefRow label="Account">
            <div class="btn-row">
              <button class="pref-btn" @click="capiConnect">
                {{ capiStatus.connected ? 'Re-authenticate' : 'Connect' }}
              </button>
              <button v-if="capiStatus.connected" class="pref-btn danger" @click="capiDisconnect">
                Disconnect
              </button>
            </div>
          </PrefRow>

          <div class="pref-sep"></div>

          <!-- EDDN -->
          <div class="pref-section">EDDN  (Elite Dangerous Data Network)</div>
          <div class="pref-note">Contribute exploration, market, and outfitting data to the shared EDDN network.</div>
          <PrefRow label="Enable EDDN" restart>
            <PrefSelect v-model="eddn.Enabled" @change="markEddn('Enabled', $event, true)" />
          </PrefRow>
          <PrefRow label="Uploader ID" restart>
            <input v-model="eddn.UploaderID" class="pref-input wide"
                   placeholder="defaults to commander name"
                   @input="markEddn('UploaderID', $event.target.value, true)" />
          </PrefRow>
          <PrefRow label="Test Mode" restart>
            <PrefSelect v-model="eddn.TestMode" @change="markEddn('TestMode', $event, true)" />
          </PrefRow>

          <div class="pref-sep"></div>

          <!-- EDSM -->
          <div class="pref-section">EDSM  (Elite Dangerous Star Map)</div>
          <div class="pref-note">Upload your flight log and discoveries to edsm.net.<br>
            Requires an EDSM account. Generate your API key at: edsm.net → Settings → API</div>
          <PrefRow label="Enable EDSM" restart>
            <PrefSelect v-model="edsm.Enabled" @change="markEdsm('Enabled', $event, true)" />
          </PrefRow>
          <PrefRow label="EDSM Commander Name" restart>
            <input v-model="edsm.CommanderName" class="pref-input wide"
                   placeholder="your EDSM commander name"
                   @input="markEdsm('CommanderName', $event.target.value, true)" />
          </PrefRow>
          <PrefRow label="EDSM API Key" restart>
            <input v-model="edsm.ApiKey" class="pref-input wide" type="password"
                   placeholder="your EDSM API key"
                   @input="markEdsm('ApiKey', $event.target.value, true)" />
          </PrefRow>

          <div class="pref-sep"></div>

          <!-- EDAstro -->
          <div class="pref-section">EDAstro</div>
          <div class="pref-note">Upload exploration, carrier, and Odyssey data to edastro.com.<br>
            Anonymous — no account or API key required.</div>
          <PrefRow label="Enable EDAstro" restart>
            <PrefSelect v-model="edastro.Enabled" @change="markEdastro('Enabled', $event, true)" />
          </PrefRow>
          <PrefRow label="Include Carrier Events  (shares carrier location)" restart>
            <PrefSelect v-model="edastro.UploadCarrierEvents"
                        @change="markEdastro('UploadCarrierEvents', $event, true)" />
          </PrefRow>

          <div class="pref-sep"></div>

          <!-- Inara -->
          <div class="pref-section">Inara</div>
          <div class="pref-note">Update your Inara profile with flight log, ranks, credits, missions, and ship loadout.<br>
            Requires an Inara account. Get your API key at: inara.cz → Settings → API</div>
          <PrefRow label="Enable Inara" restart>
            <PrefSelect v-model="inara.Enabled" @change="markInara('Enabled', $event, true)" />
          </PrefRow>
          <PrefRow label="Commander Name" restart>
            <input v-model="inara.CommanderName" class="pref-input wide"
                   placeholder="your in-game commander name"
                   @input="markInara('CommanderName', $event.target.value, true)" />
          </PrefRow>
          <PrefRow label="Inara API Key" restart>
            <input v-model="inara.ApiKey" class="pref-input wide" type="password"
                   placeholder="your Inara API key"
                   @input="markInara('ApiKey', $event.target.value, true)" />
          </PrefRow>

          <!-- Raven Colonial -->
          <div class="pref-section">Raven Colonial</div>
          <div class="pref-note">
            Sync colonisation construction supply needs and deliveries to
            <strong>ravencolonial.com</strong> so other commanders can see
            live project progress.<br>
            Leave blank to disable — local tracking always works without an API key.<br>
            Get your API key at: ravencolonial.com → Account Settings
          </div>
          <PrefRow label="Raven Colonial API Key">
            <input v-model="raven.ApiKey" class="pref-input wide" type="password"
                   placeholder="optional — your Raven Colonial API key"
                   @input="markRaven('ApiKey', $event.target.value)" />
          </PrefRow>
        </div>
      </div>

      <div class="prefs-footer">
        <span v-if="restartNeeded" class="restart-note">⚠ Restart required for marked changes</span>
        <span v-else></span>
        <button class="btn-cancel" @click="$emit('close')">Cancel</button>
        <button class="btn-apply" @click="apply">
          {{ restartNeeded ? 'Apply & Restart' : 'Apply & Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import PrefRow    from './PrefRow.vue';
import PrefSelect from './PrefSelect.vue';

const emit = defineEmits(['close', 'send']);

// Open Setup tab first when there is a startup error
const params      = new URLSearchParams(window.location.search);
const startupErr  = params.get('startupError');
const activeTab   = ref(startupErr ? 'setup' : 'general');
const startupErrorMsg = startupErr ? JSON.parse(decodeURIComponent(startupErr)).message : '';
const tabs = [
  { id: 'setup',         label: 'Setup'                },
  { id: 'general',       label: 'General'              },
  { id: 'notifications', label: 'Notifications'        },
  { id: 'appearance',    label: 'Appearance'           },
  { id: 'data',          label: 'Data & Integrations'  },
];

const themes = [
  'default', 'default-dark', 'default-green',
  'default-blue', 'default-purple', 'default-red', 'default-yellow',
];

const pending = reactive({});
const restartNeeded = ref(false);
const dirty = computed(() => Object.keys(pending).length > 0);

const s        = reactive({});
const nl       = reactive({});
const ui       = reactive({});
const edmdCfg  = reactive({ edmdPath: '', pythonPath: '', profile: '', extraArgs: '' });
const eddn     = reactive({ Enabled: false, UploaderID: '', TestMode: false });
const edsm     = reactive({ Enabled: false, CommanderName: '', ApiKey: '' });
const inara    = reactive({ Enabled: false, CommanderName: '', ApiKey: '' });
const edastro  = reactive({ Enabled: false, UploadCarrierEvents: false });
const raven    = reactive({ ApiKey: '' });
const capiStatus = reactive({ state: 'Checking…', connected: false });

let capiPollTimer = null;

const notifEntries = [
  { key: 'RewardEvent',    label: 'Kill reward'             },
  { key: 'FighterDamage',  label: 'Fighter hull damage'     },
  { key: 'FighterLost',    label: 'Fighter destroyed'       },
  { key: 'ShieldEvent',    label: 'Shield raised / dropped' },
  { key: 'HullEvent',      label: 'Ship hull damaged'       },
  { key: 'Died',           label: 'Ship destroyed'          },
  { key: 'CargoLost',      label: 'Cargo stolen'            },
  { key: 'LowCargoValue',  label: 'Low cargo value'         },
  { key: 'PoliceScan',     label: 'Security scan'           },
  { key: 'PoliceAttack',   label: 'Security attack'         },
  { key: 'FuelStatus',     label: 'Fuel status (routine)'   },
  { key: 'FuelWarning',    label: 'Fuel warning'            },
  { key: 'FuelCritical',   label: 'Fuel critical'           },
  { key: 'MissionUpdate',  label: 'Mission update'          },
  { key: 'AllMissionsReady', label: 'All missions ready'    },
  { key: 'MeritEvent',     label: 'Merit gain'              },
];

function mark(key, value, restart = false) {
  pending[`settings.${key}`] = { section: 'settings', key, value };
  if (restart) restartNeeded.value = true;
}
function markNl(key, value) { pending[`notify.${key}`] = { section: 'notify_levels', key, value }; }
function markUi(key, value, restart = false) {
  pending[`ui.${key}`] = { section: 'ui', key, value };
  if (restart) restartNeeded.value = true;
}
function markEddn(key, value, restart = false) {
  pending[`eddn.${key}`] = { section: 'eddn', key, value };
  if (restart) restartNeeded.value = true;
}
function markEdsm(key, value, restart = false) {
  pending[`edsm.${key}`] = { section: 'edsm', key, value };
  if (restart) restartNeeded.value = true;
}
function markInara(key, value, restart = false) {
  pending[`inara.${key}`] = { section: 'inara', key, value };
  if (restart) restartNeeded.value = true;
}
function markEdastro(key, value, restart = false) {
  pending[`edastro.${key}`] = { section: 'edastro', key, value };
  if (restart) restartNeeded.value = true;
}
function markRaven(key, value) {
  pending[`raven.${key}`] = { section: 'colonisation', key, value };
}

function capiConnect()    { emit('send', { cmd: 'capi_connect' }); pollCapiStatus(); }
function capiDisconnect() { emit('send', { cmd: 'capi_disconnect' }); pollCapiStatus(); }
function pollCapiStatus() {
  emit('send', { cmd: 'get_prefs' });
}

function markEdmdCfg(key, value) {
  edmdCfg[key] = value;
  pending[`edmd.${key}`] = { section: 'edmd', key, value };
}
async function browseEdmdPy() {
  const p = await window.edmd?.browseFile?.({ title: 'Select edmd.py' });
  if (p) { edmdCfg.edmdPath = p; markEdmdCfg('edmdPath', p); }
}
async function browsePython() {
  const ext = navigator.platform.startsWith('Win') ? ['exe'] : ['*'];
  const p = await window.edmd?.browseFile?.({
    title: 'Select Python interpreter',
    filters: [{ name: 'Python', extensions: ext }],
  });
  if (p) { edmdCfg.pythonPath = p; markEdmdCfg('pythonPath', p); }
}

function apply() {
  // Save Electron-side config (edmdPath, profile, etc.) directly — not through bridge
  const edmdChanges = Object.values(pending).filter(c => c.section === 'edmd');
  if (edmdChanges.length) {
    const update = {};
    edmdChanges.forEach(c => { update[c.key] = c.value; });
    // Merge with existing stored config
    window.edmd?.getEdmdConfig?.().then(existing => {
      window.edmd?.saveEdmdConfig?.({ ...(existing || {}), ...update });
    });
  }
  const bridgeChanges = Object.values(pending).filter(c => c.section !== 'edmd');
  if (bridgeChanges.length) {
    emit('send', { cmd: 'save_prefs', changes: bridgeChanges, restart: restartNeeded.value });
  }
  emit('close');
}

onMounted(() => {
  emit('send', { cmd: 'get_prefs' });
  // Load Electron-side config once on open (path, profile etc.)
  window.edmd?.getEdmdConfig?.().then(cfg => {
    if (cfg) Object.assign(edmdCfg, cfg);
  });
  // Poll CAPI status every 3s while prefs are open (only when Data tab is visible)
  capiPollTimer = setInterval(() => {
    if (activeTab.value === 'data') emit('send', { cmd: 'get_prefs' });
  }, 3000);
});

// Cleanup on unmount
import { onUnmounted } from 'vue';
onUnmounted(() => { if (capiPollTimer) clearInterval(capiPollTimer); });

defineExpose({ applyPrefsData(data) {
  Object.assign(s,       data.settings        || {});
  Object.assign(nl,      data.notify_levels   || {});
  Object.assign(ui,      data.ui_cfg          || {});
  Object.assign(eddn,    data.eddn_cfg        || {});
  Object.assign(edsm,    data.edsm_cfg        || {});
  Object.assign(inara,   data.inara_cfg          || {});
  Object.assign(edastro, data.edastro_cfg         || {});
  Object.assign(raven,   data.colonisation_cfg    || {});
  if (data.capi_status) Object.assign(capiStatus, data.capi_status);
}});
</script>

<style scoped>
.panel-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.prefs-window {
  background: var(--bg-panel); border: 1px solid var(--border-accent);
  border-radius: 3px; width: min(820px, 94vw); max-height: 88vh;
  display: flex; flex-direction: column;
}
.prefs-header {
  background: var(--bg-header); color: var(--accent); font-weight: bold;
  font-size: 12px; padding: 6px 12px; display: flex; align-items: center;
  border-bottom: 1px solid var(--border);
}
.close-btn { margin-left: auto; background: none; border: none; color: var(--text-dim); cursor: pointer; font-size: 14px; }
.close-btn:hover { color: var(--text); }
.prefs-body { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.tab-bar {
  display: flex; border-bottom: 1px solid var(--border);
  background: var(--bg-header); padding: 0 8px; flex-shrink: 0;
}
.tab-btn {
  background: none; border: none; border-bottom: 2px solid transparent;
  color: var(--text-dim); cursor: pointer; padding: 6px 12px; font-size: 11px;
  font-family: inherit; text-transform: uppercase; letter-spacing: 0.04em;
}
.tab-btn.active  { color: var(--accent); border-bottom-color: var(--accent); }
.tab-btn:hover:not(.active) { color: var(--text); }
.tab-content  { flex: 1; overflow-y: auto; padding: 8px 12px; }
.pref-section { color: var(--accent); font-size: 10px; text-transform: uppercase;
                letter-spacing: 0.08em; margin: 10px 0 4px; }
.pref-note    { color: var(--text-dim); font-size: 11px; margin-bottom: 6px; line-height: 1.5; }
.pref-sep     { height: 1px; background: var(--border); margin: 10px 0; }
.pref-input   { background: var(--bg-input); border: 1px solid var(--border);
                color: var(--text); font-family: inherit; font-size: 12px;
                padding: 2px 6px; border-radius: 2px; }
.pref-input.wide   { width: 100%; }
.pref-input.narrow  { width: 72px; }
.pref-input.widest  { width: 100%; min-width: 400px; }
.pref-select  { background: var(--bg-input); border: 1px solid var(--border);
                color: var(--text); font-family: inherit; font-size: 12px;
                padding: 2px 6px; border-radius: 2px; }
.capi-status          { color: var(--text-dim); font-size: 11px; }
.capi-status.connected{ color: var(--health-good); }
.btn-row { display: flex; gap: 8px; }
.pref-btn { padding: 3px 12px; border-radius: 2px; font-family: inherit; font-size: 11px;
            cursor: pointer; background: var(--bg); border: 1px solid var(--border);
            color: var(--text); }
.pref-btn:hover  { border-color: var(--accent); color: var(--accent); }
.pref-btn.danger { border-color: var(--health-crit); color: var(--health-crit); }
.pref-btn.danger:hover { background: var(--health-crit); color: #000; }
.pref-btn.browse-btn  { margin-left: 6px; white-space: nowrap; flex-shrink: 0; }
.startup-error { background: rgba(192,57,43,0.15); border: 1px solid var(--health-crit);
                 border-radius: 3px; padding: 10px 14px; margin-bottom: 12px; display: flex;
                 align-items: flex-start; gap: 10px; }
.error-icon    { color: var(--health-crit); font-size: 18px; flex-shrink: 0; }
.error-text    { margin: 0; font-size: 11px; color: var(--text); white-space: pre-wrap; }
.prefs-footer {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-top: 1px solid var(--border);
  background: var(--bg-header); flex-shrink: 0;
}
.restart-note { color: var(--health-warn); font-size: 11px; flex: 1; }
.btn-cancel, .btn-apply {
  padding: 4px 14px; border-radius: 2px; font-family: inherit;
  font-size: 12px; cursor: pointer; border: 1px solid var(--border);
}
.btn-cancel { background: var(--bg); color: var(--text-dim); }
.btn-cancel:hover { color: var(--text); }
.btn-apply  { background: var(--accent); color: #000; border-color: var(--accent-bright); }
.btn-apply:hover:not(:disabled) { background: var(--accent-bright); }
.btn-apply:disabled { opacity: 0.4; cursor: default; }
</style>
