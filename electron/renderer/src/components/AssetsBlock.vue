<template>
  <div class="panel">
    <div class="panel-header">
      ASSETS
      <span v-if="d.net_worth" class="net-hdr">{{ fmtCr(d.net_worth) }}</span>
    </div>

    <TabSet :tabs="tabs" style="flex:1;min-height:0;">
      <!-- Wallet -->
      <template #wallet>
        <div class="sec-hdr">Currencies</div>
        <div class="kv"><span class="k">Credits</span>
          <span class="v accent">{{ fmtCr(d.balance) }}</span></div>

        <div class="sec-hdr">Fleet</div>
        <div class="kv"><span class="k">Ships</span>
          <span class="v">{{ fmtCr(d.ships_value) }}</span></div>
        <div class="kv"><span class="k">Modules</span>
          <span class="v">{{ fmtCr(d.mods_value) }}</span></div>

        <template v-if="d.carrier">
          <div class="sec-hdr">Fleet Carrier</div>
          <div class="kv" v-if="d.carrier.balance">
            <span class="k">Balance</span>
            <span class="v">{{ fmtCr(d.carrier.balance) }}</span></div>
          <div class="kv"><span class="k">Hull</span>
            <span class="v">{{ fmtCr(d.carrier.hull_value) }}</span></div>
          <div class="kv" v-if="d.carrier.cargo_value">
            <span class="k">Market listings</span>
            <span class="v">{{ fmtCr(d.carrier.cargo_value) }}</span></div>
        </template>

        <div class="sec-hdr">Assets At Risk</div>
        <div class="kv"><span class="k">Bounties</span>
          <span class="v">{{ fmtCr(d.risk?.bounties) }}</span></div>
        <div class="kv"><span class="k">Combat bonds</span>
          <span class="v">{{ fmtCr(d.risk?.bonds) }}</span></div>
        <div class="kv"><span class="k">Trade vouchers</span>
          <span class="v">{{ fmtCr(d.risk?.trade) }}</span></div>
        <div class="kv"><span class="k">Cartography (est.)</span>
          <span class="v">{{ fmtCr(d.risk?.carto) }}</span></div>
        <div class="kv"><span class="k">Exobiology (est.)</span>
          <span class="v">{{ fmtCr(d.risk?.exobio) }}</span></div>

        <div class="sep"></div>
        <div class="kv nw">
          <span class="nw-k">Net Worth</span>
          <span class="v">{{ fmtCr(d.net_worth) }}</span>
        </div>
        <div v-if="d.balance == null" class="dim padded">Awaiting CAPI data</div>
      </template>

      <!-- Ships -->
      <template #ships>
        <template v-if="d.current_ship">
          <div class="sec-hdr">Current  ★</div>
          <div class="ship-row" :title="modulesTooltip(d.current_ship)">
            <span class="ship-name">{{ shipLabel(d.current_ship) }}</span>
            <span class="ship-sys dim">{{ d.current_ship.system }}</span>
          </div>
          <div class="kv sub" v-if="d.current_ship.value">
            <span class="k">Value</span>
            <span class="v">{{ fmtCr(d.current_ship.value) }}</span></div>
        </template>
        <template v-if="d.stored_ships?.length">
          <div class="sec-hdr">Stored ({{ d.stored_ships.length }})</div>
          <div v-for="s in d.stored_ships" :key="s.system+s.type+s.name"
               class="ship-row" :class="{ hot: s.hot }"
               :title="modulesTooltip(s)">
            <span class="ship-name">{{ shipLabel(s) }}</span>
            <span class="ship-sys dim">{{ s.system }}</span>
          </div>
        </template>
        <div v-if="!d.current_ship && !d.stored_ships?.length" class="dim padded">
          Awaiting CAPI data
        </div>
      </template>

      <!-- Modules — full list grouped by category -->
      <template #modules>
        <div v-if="!hasModules" class="dim padded">
          Open outfitting at a station to populate stored modules.
        </div>
        <template v-else>
          <template v-for="(mods, cat) in d.modules" :key="cat">
            <div class="sec-hdr">{{ cat }}</div>
            <div v-for="m in mods" :key="m.name+m.system" class="mod-row"
                 :class="{ hot: m.hot }">
              <span class="mod-name">{{ m.name }}
                <span v-if="m.eng" class="mod-eng">  {{ m.eng }}</span>
              </span>
              <span class="mod-sys dim">{{ m.system }}</span>
              <span class="mod-val">{{ fmtCr(m.value) }}</span>
            </div>
          </template>
        </template>
      </template>

      <!-- Fleet Carrier -->
      <template #carrier>
        <div v-if="!d.carrier" class="dim padded">No fleet carrier data</div>
        <template v-else>
          <div class="kv"><span class="k">Name</span>
            <span class="v">{{ d.carrier.name || '—' }}</span></div>
          <div class="kv"><span class="k">Callsign</span>
            <span class="v">{{ d.carrier.callsign || '—' }}</span></div>
          <div class="kv"><span class="k">System</span>
            <span class="v">{{ d.carrier.system || '—' }}</span></div>
          <div class="kv" v-if="d.carrier.fuel != null">
            <span class="k">Fuel</span>
            <span class="v">{{ d.carrier.fuel }}/1000  ({{ Math.round(d.carrier.fuel/10) }}%)</span>
          </div>
          <div class="kv" v-if="d.carrier.state">
            <span class="k">State</span>
            <span class="v">{{ d.carrier.state }}</span></div>
          <div class="sec-hdr">Finance</div>
          <div class="kv"><span class="k">Balance</span>
            <span class="v">{{ fmtCr(d.carrier.balance) }}</span></div>
          <div class="kv" v-if="d.carrier.reserve">
            <span class="k">Reserve</span>
            <span class="v">{{ fmtCr(d.carrier.reserve) }}</span></div>
          <div class="kv" v-if="d.carrier.available">
            <span class="k">Available</span>
            <span class="v">{{ fmtCr(d.carrier.available) }}</span></div>
          <div class="kv"><span class="k">Hull (decommission)</span>
            <span class="v">{{ fmtCr(d.carrier.hull_value) }}</span></div>
          <div class="sec-hdr">Cargo</div>
          <div class="kv" v-if="d.carrier.cargo_used != null">
            <span class="k">Stored</span>
            <span class="v">{{ d.carrier.cargo_used?.toLocaleString() }} t</span></div>
          <div class="kv" v-if="d.carrier.cargo_free != null">
            <span class="k">Free</span>
            <span class="v">{{ d.carrier.cargo_free?.toLocaleString() }} t</span></div>
          <div class="kv" v-if="d.carrier.cargo_value">
            <span class="k">Market listings</span>
            <span class="v accent">{{ fmtCr(d.carrier.cargo_value) }}</span></div>
        </template>
      </template>
    </TabSet>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TabSet from './TabSet.vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const d = computed(() => props.data);

const hasModules = computed(() =>
  d.value.modules && Object.keys(d.value.modules).length > 0
);

const shipsLabel = computed(() => {
  const n = (d.value.stored_ships?.length || 0) + (d.value.current_ship ? 1 : 0);
  return n ? `Ships (${n})` : 'Ships';
});
const modsLabel = computed(() =>
  d.value.module_count ? `Modules (${d.value.module_count})` : 'Modules'
);
const tabs = computed(() => [
  { id: 'wallet',  label: 'Wallet'         },
  { id: 'ships',   label: shipsLabel.value },
  { id: 'modules', label: modsLabel.value  },
  { id: 'carrier', label: 'Fleet Carrier'  },
]);

function fmtCr(n) {
  if (n == null || n === 0) return '—';
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B cr';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M cr';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'k cr';
  return n.toLocaleString() + ' cr';
}

function shipLabel(s) {
  if (!s) return '—';
  // type is always the localised display name from type_display
  let label = s.type || '—';
  if (s.name)  label += `  "${s.name}"`;
  if (s.ident) label += `  / ${s.ident}`;
  return label;
}

function modulesTooltip(ship) {
  const mods = ship?.modules;
  if (!mods?.length) return '';
  return mods.join('\n');
}
</script>

<style scoped>
.net-hdr  { margin-left: auto; color: var(--text-dim); font-size: 11px; font-weight: normal; }
.kv       { display: flex; align-items: baseline; padding: 1px 0; font-size: 12px; gap: 6px; }
.k        { color: var(--text-dim); font-size: 11px; flex: 1; white-space: nowrap; }
.v        { text-align: right; }
.accent   { color: var(--accent); }
.sub      { padding-left: 8px; }
.sec-hdr  { color: var(--accent); font-size: 10px; text-transform: uppercase;
            letter-spacing: 0.06em; margin: 5px 0 1px; }
.sep      { height: 1px; background: var(--border); margin: 5px 0 3px; }
.nw .nw-k { font-weight: bold; font-size: 12px; flex: 1; color: var(--text); }

.ship-row { display: flex; align-items: baseline; padding: 2px 0;
            font-size: 11px; gap: 6px; cursor: default;
            border-bottom: 1px solid var(--border); }
.ship-row:hover { background: var(--bg-hover); }
.ship-row.hot .ship-name { color: var(--health-warn); }
.ship-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ship-sys  { font-size: 10px; flex-shrink: 0; }

.mod-row  { display: flex; align-items: baseline; padding: 1px 0;
            font-size: 11px; gap: 4px;
            border-bottom: 1px solid transparent; }
.mod-row:hover { background: var(--bg-hover); }
.mod-row.hot .mod-name { color: var(--health-warn); }
.mod-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mod-eng  { color: var(--accent); font-size: 10px; }
.mod-sys  { font-size: 10px; flex-shrink: 0; max-width: 80px;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mod-val  { font-size: 10px; text-align: right; min-width: 52px; flex-shrink: 0; }

.dim      { color: var(--text-dim); }
.padded   { padding: 6px 0; text-align: center; font-size: 11px; }
</style>
