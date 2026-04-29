<template>
  <div class="panel">
    <!-- GTK4-matching two-line header -->
    <div class="panel-header cmdr-hdr">
      <div class="hdr-col-left">
        <div class="hdr-line1">{{ cmdrLine1 }}</div>
        <div v-if="hdrLine2Left" class="hdr-line2">{{ hdrLine2Left }}</div>
      </div>
      <div class="hdr-col-right">
        <div class="hdr-line1-r">{{ shipLine1 }}</div>
        <div v-if="hdrLine2Right" class="hdr-line2-r">{{ hdrLine2Right }}</div>
      </div>
    </div>

    <TabSet :tabs="tabs" style="flex:1;min-height:0;">
      <!-- ── Info ───────────────────────────────────────────────────────── -->
      <template #info>
        <div class="grid">
          <span class="k">Shields</span>
          <span class="v" :class="shieldCls">{{ shieldText }}</span>
          <span class="k">{{ hullLabel }}</span>
          <span class="v" :class="hullCls">{{ hullText }}</span>
          <template v-if="showFuel">
            <span class="k">Fuel</span>
            <span class="v" :class="fuelCls">{{ fuelText }}</span>
          </template>
          <span class="sep-full"></span>
          <span class="k">Mode</span>
          <span class="v">{{ d.pilot_mode || '—' }}</span>
          <!-- Home System: always show when commander plugin loaded (d._home not null)
               Shows "unknown" when not set, display string when set — matching GTK4 -->
          <template v-if="d._home != null">
            <span class="k">Home System</span>
            <span class="v dim">{{ d._home.display || 'unknown' }}</span>
          </template>
          <template v-if="d.pilot_system">
            <span class="k">Current System</span>
            <span class="v">{{ d.pilot_system }}</span>
          </template>
          <template v-if="d.pilot_body_local">
            <span class="k">Location</span>
            <span class="v">{{ d.pilot_body_local }}</span>
          </template>
          <template v-if="d.pp_power">
            <span class="k">Power</span>
            <span class="v">{{ d.pp_power }}</span>
            <span class="k">PP Rank</span>
            <span class="v">Rank {{ d.pp_rank }}  {{ ppPct }}%</span>
          </template>
        </div>
        <div v-if="d.pp_power && d.pp_rank" class="pp-bar-outer">
          <div class="pp-bar-inner" :style="{ width: (d.pp_rank_fraction || 0) * 100 + '%' }"></div>
        </div>

        <!-- Home system search (matching GTK4 footer search) -->
        <div class="home-search-area">
          <SpanshSearch
            ref="homeSearch"
            placeholder="Set Home Location…"
            search-cmd="search_home"
            :initial-text="''"
            @pick="onHomePick"
            @clear="onHomeClear"
            @send="$emit('send', $event)"
          />
        </div>
      </template>

      <!-- ── Ranks ──────────────────────────────────────────────────────── -->
      <template #ranks>
        <div v-if="!d.capi_ranks" class="dim padded">Awaiting CAPI data…</div>
        <div v-else class="grid">
          <template v-for="r in d.capi_ranks" :key="r.key">
            <span class="k">{{ r.label }}</span>
            <span class="v">{{ r.name }}{{ r.progress != null ? `  +${r.progress}%` : '' }}</span>
          </template>
        </div>
      </template>

      <!-- ── Rep ────────────────────────────────────────────────────────── -->
      <template #rep>
        <div v-if="!d.capi_reputation" class="dim padded">Awaiting login data…</div>
        <template v-else>
          <div class="sec-hdr">Major Factions</div>
          <div class="grid">
            <template v-for="(val, faction) in majorFactions" :key="faction">
              <span class="k">{{ faction }}</span>
              <span class="v" :class="repCls(val)">{{ val.toFixed(1) }}%</span>
            </template>
          </div>
        </template>
      </template>
    </TabSet>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import TabSet       from './TabSet.vue';
import SpanshSearch from './SpanshSearch.vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const emit  = defineEmits(['send']);
const d = computed(() => props.data);
const homeSearch = ref(null);

const tabs = [
  { id: 'info',  label: 'Info'  },
  { id: 'ranks', label: 'Ranks' },
  { id: 'rep',   label: 'Rep'   },
];

const MAJOR = ['Federation', 'Empire', 'Alliance', 'Independent'];
const majorFactions = computed(() => {
  const rep = d.value.capi_reputation || {};
  return Object.fromEntries(MAJOR.filter(f => f in rep).map(f => [f, rep[f]]));
});

// Header construction matching GTK4 exactly
const cmdrLine1 = computed(() => {
  const n = d.value.pilot_name;
  if (!n) return 'COMMANDER';
  const sqRank = d.value.pilot_squadron_rank;
  const vm     = d.value.vessel_mode || 'ship';
  if (sqRank)               return `CMDR ${n}  —  ${sqRank.toUpperCase()}`;
  if (d.value.cmdr_in_slf)  return `CMDR ${n}  [IN FIGHTER]`;
  if (vm === 'on_foot')     return `CMDR ${n}  [ON FOOT]`;
  if (vm === 'srv')         return `CMDR ${n}  [IN SRV]`;
  return `CMDR ${n}`;
});
const shipLine1 = computed(() => {
  const vm = d.value.vessel_mode || 'ship';
  if (vm === 'on_foot') return (d.value.suit_name || 'ON FOOT').toUpperCase();
  if (vm === 'srv')     return 'SRV';
  return (d.value.pilot_ship || '').toUpperCase();
});
const hdrLine2Left = computed(() => {
  const name = d.value.pilot_squadron_name;
  const tag  = d.value.pilot_squadron_tag;
  if (!name) return '';
  return tag ? `${name.toUpperCase()}  [${tag.toUpperCase()}]` : name.toUpperCase();
});
const hdrLine2Right = computed(() => {
  const parts = [d.value.ship_name, d.value.ship_ident].filter(Boolean);
  return parts.join(' | ');
});

// Vitals
const shieldText = computed(() => {
  const vm = d.value.vessel_mode || 'ship';
  if (vm === 'srv') return '—';
  const up = d.value.ship_shields;
  const rc = d.value.ship_shields_recharging;
  if (up == null) return '—';
  return up ? 'Up' : (rc ? 'Recharging' : 'Down');
});
const shieldCls = computed(() => {
  const vm = d.value.vessel_mode || 'ship';
  if (vm === 'srv') return '';
  const up = d.value.ship_shields;
  if (up == null) return '';
  return up ? 'good' : (d.value.ship_shields_recharging ? 'warn' : 'crit');
});
const hullLabel = computed(() => (d.value.vessel_mode || 'ship') === 'on_foot' ? 'Health' : 'Hull');
const hullText  = computed(() => {
  const vm  = d.value.vessel_mode || 'ship';
  if (vm === 'on_foot') return '—';
  const pct = vm === 'srv' ? d.value.srv_hull : d.value.ship_hull;
  return pct != null ? `${pct}%` : '—';
});
const hullCls = computed(() => {
  const vm  = d.value.vessel_mode || 'ship';
  const pct = vm === 'srv' ? d.value.srv_hull : d.value.ship_hull;
  if (pct == null) return '';
  return pct > 75 ? 'good' : pct >= 25 ? 'warn' : 'crit';
});
const showFuel = computed(() => d.value.fuel_current != null && (d.value.vessel_mode || 'ship') === 'ship');
const fuelText = computed(() => {
  const cur = d.value.fuel_current; const tank = d.value.fuel_tank_size || 64;
  const pct = Math.round(cur / tank * 100);
  const rate = d.value.fuel_burn_rate;
  if (rate && rate > 0) {
    const secs = cur / rate * 3600;
    const h = Math.floor(secs / 3600); const m = Math.floor((secs % 3600) / 60);
    return `${pct}%  (~${h}h ${m}m)`;
  }
  return `${pct}%  (${cur.toFixed(1)} t)`;
});
const fuelCls = computed(() => {
  const cur = d.value.fuel_current; const tank = d.value.fuel_tank_size || 64;
  const pct = cur / tank;
  return pct < 0.15 ? 'crit' : pct < 0.25 ? 'warn' : 'good';
});
const ppPct = computed(() => Math.round((d.value.pp_rank_fraction || 0) * 100));

// Home display text
const homeDisplay = computed(() => d.value._home?.set ? (d.value._home?.name || '') : '');

function onHomePick(result) {
  emit('send', {
    cmd:      'set_home',
    name:     result.name,
    system:   result.system || result.name,
    star_pos: result.star_pos || null,
  });
  // reset() clears the field without emitting 'clear' (which would undo the pick)
  homeSearch.value?.reset();
  // Release keyboard focus back to the window
  document.activeElement?.blur?.();
}
function onHomeClear() {
  emit('send', { cmd: 'clear_home' });
}

function repCls(val) {
  return val >= 50 ? 'good' : val >= 0 ? '' : val >= -50 ? 'warn' : 'crit';
}
</script>

<style scoped>
/* Header */
.cmdr-hdr       { display: flex; align-items: flex-start; padding: 4px 6px; min-height: 34px; }
.hdr-col-left   { flex: 1; min-width: 0; overflow: hidden; }
.hdr-col-right  { text-align: right; flex-shrink: 0; padding-left: 4px; }
.hdr-line1      { font-size: 12px; font-weight: bold; color: var(--accent); line-height: 1.3;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hdr-line1-r    { font-size: 12px; color: var(--accent); font-weight: bold; line-height: 1.3; }
.hdr-line2      { font-size: 10px; color: var(--accent);   line-height: 1.2; }
.hdr-line2-r    { font-size: 10px; color: var(--accent);   line-height: 1.2; text-align: right; }

/* Info grid */
.grid { display: grid; grid-template-columns: auto 1fr; column-gap: 8px; row-gap: 2px; font-size: 12px; }
.k    { color: var(--text-dim); font-size: 11px; white-space: nowrap; align-self: center; }
.v    { text-align: right; align-self: center; }
.dim  { color: var(--text-dim); }
.sep-full { grid-column: 1 / -1; height: 4px; }
.good { color: var(--health-good); }
.warn { color: var(--health-warn); }
.crit { color: var(--health-crit); }

/* PP bar */
.pp-bar-outer { height: 4px; background: var(--bg); border: 1px solid var(--border);
                border-radius: 2px; overflow: hidden; margin: 3px 0 4px; }
.pp-bar-inner { height: 100%; background: var(--accent); transition: width 0.4s; }

/* Home search */
.home-search-area { margin-top: 6px; border-top: 1px solid var(--border); padding-top: 5px; }

/* Ranks/Rep */
.sec-hdr { color: var(--accent); font-size: 10px; text-transform: uppercase;
           letter-spacing: 0.06em; margin: 5px 0 2px; }
.padded  { padding: 8px 0; text-align: center; font-size: 11px; }
</style>
