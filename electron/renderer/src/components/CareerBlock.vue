<template>
  <div class="panel">
    <div class="panel-header">Career</div>

    <TabSet :tabs="tabs" style="flex:1;min-height:0;">

      <!-- Summary — mirrors old GTK4 summary_box section headers -->
      <template #summary>
        <div v-if="d.scanning" class="dim padded">Scanning journals…</div>
        <template v-else>
          <div class="kv-row" v-if="d.time_played">
            <span class="k">Time played</span>
            <span class="v">{{ fmtDur(d.time_played) }}</span>
          </div>
          <template v-if="d.kills || d.bounties">
            <div class="sec-hdr">Combat</div>
            <div class="kv-row">
              <span class="k">Kills</span>
              <span class="v">{{ fmt(d.kills) }}</span>
              <span class="rate">{{ fmtCr(d.bounties) }}</span>
            </div>
          </template>
          <template v-if="d.systems_visited || d.carto_sold">
            <div class="sec-hdr">Exploration</div>
            <div class="kv-row">
              <span class="k">Systems</span>
              <span class="v">{{ fmt(d.systems_visited) }}</span>
              <span class="rate">{{ fmtCr(d.carto_sold) }}</span>
            </div>
          </template>
          <template v-if="d.exo_samples || d.exo_sold">
            <div class="sec-hdr">Exobiology</div>
            <div class="kv-row">
              <span class="k">Samples</span>
              <span class="v">{{ fmt(d.exo_samples) }}</span>
              <span class="rate">{{ fmtCr(d.exo_sold) }}</span>
            </div>
          </template>
          <template v-if="d.qty_mined || d.mining_profit">
            <div class="sec-hdr">Mining</div>
            <div class="kv-row">
              <span class="k">Mined</span>
              <span class="v">{{ fmt(d.qty_mined) }} t</span>
              <span class="rate">{{ fmtCr(d.mining_profit) }}</span>
            </div>
          </template>
          <template v-if="d.trade_profit">
            <div class="sec-hdr">Trade</div>
            <div class="kv-row">
              <span class="k">Profit</span>
              <span class="v">{{ fmtCr(d.trade_profit) }}</span>
            </div>
          </template>
          <template v-if="d.pp_merits && d.pp_power">
            <div class="sec-hdr">PowerPlay</div>
            <div class="kv-row">
              <span class="k">Merits</span>
              <span class="v">{{ fmt(d.pp_merits) }}</span>
            </div>
          </template>
        </template>
      </template>

      <!-- Combat -->
      <template #combat>
        <div class="kv-row" v-if="d.kills">
          <span class="k">Kills</span><span class="v">{{ fmt(d.kills) }}</span></div>
        <div class="kv-row" v-if="d.bounties">
          <span class="k">Bounties earned</span><span class="v">{{ fmtCr(d.bounties) }}</span></div>
        <div class="kv-row" v-if="d.bonds">
          <span class="k">Combat bonds</span><span class="v">{{ fmtCr(d.bonds) }}</span></div>
        <div class="kv-row" v-if="d.assassinations">
          <span class="k">Assassinations</span><span class="v">{{ fmt(d.assassinations) }}</span></div>
        <div class="kv-row" v-if="d.deaths">
          <span class="k">Deaths</span><span class="v warn">{{ fmt(d.deaths) }}</span></div>
        <div class="kv-row" v-if="d.rebuy_costs">
          <span class="k">Rebuy costs</span><span class="v">{{ fmtCr(d.rebuy_costs) }}</span></div>
      </template>

      <!-- Explore -->
      <template #explore>
        <div class="kv-row" v-if="d.systems_visited">
          <span class="k">Systems visited</span><span class="v">{{ fmt(d.systems_visited) }}</span></div>
        <div class="kv-row" v-if="d.hyperspace_jumps">
          <span class="k">Hyperspace jumps</span><span class="v">{{ fmt(d.hyperspace_jumps) }}</span></div>
        <div class="kv-row" v-if="d.distance_ly">
          <span class="k">Distance</span><span class="v">{{ Math.round(d.distance_ly).toLocaleString() }} ly</span></div>
        <div class="kv-row" v-if="d.planets_fss">
          <span class="k">Planets FSS</span><span class="v">{{ fmt(d.planets_fss) }}</span></div>
        <div class="kv-row" v-if="d.planets_dss">
          <span class="k">Planets DSS</span><span class="v">{{ fmt(d.planets_dss) }}</span></div>
        <div class="kv-row" v-if="d.first_footfalls">
          <span class="k">First footfalls</span><span class="v">{{ fmt(d.first_footfalls) }}</span></div>
        <div class="kv-row" v-if="d.carto_sold">
          <span class="k">Exploration profit</span><span class="v">{{ fmtCr(d.carto_sold) }}</span></div>
        <div class="kv-row" v-if="d.carto_highest">
          <span class="k">Highest payout</span><span class="v">{{ fmtCr(d.carto_highest) }}</span></div>
      </template>

      <!-- Exobio -->
      <template #exobio>
        <div class="kv-row" v-if="d.exo_samples">
          <span class="k">Samples analysed</span><span class="v">{{ fmt(d.exo_samples) }}</span></div>
        <div class="kv-row" v-if="d.exo_species">
          <span class="k">Species found</span><span class="v">{{ fmt(d.exo_species) }}</span></div>
        <div class="kv-row" v-if="d.exo_genus">
          <span class="k">Genus found</span><span class="v">{{ fmt(d.exo_genus) }}</span></div>
        <div class="kv-row" v-if="d.exo_systems">
          <span class="k">Systems</span><span class="v">{{ fmt(d.exo_systems) }}</span></div>
        <div class="kv-row" v-if="d.exo_planets">
          <span class="k">Planets</span><span class="v">{{ fmt(d.exo_planets) }}</span></div>
        <div class="kv-row" v-if="d.exo_sold">
          <span class="k">Total sold</span><span class="v">{{ fmtCr(d.exo_sold) }}</span></div>
        <div class="kv-row" v-if="d.exo_first_logged">
          <span class="k">First logged</span><span class="v">{{ fmt(d.exo_first_logged) }}</span></div>
        <div class="kv-row" v-if="d.exo_first_profit">
          <span class="k">First logged profits</span><span class="v">{{ fmtCr(d.exo_first_profit) }}</span></div>
      </template>

      <!-- Mining -->
      <template #mining>
        <div class="kv-row"><span class="k">Tonnes mined</span><span class="v">{{ fmt(d.qty_mined) }}</span></div>
        <div class="kv-row"><span class="k">Mining profits</span><span class="v">{{ fmtCr(d.mining_profit) }}</span></div>
        <div class="kv-row" v-if="d.mining_materials">
          <span class="k">Materials</span><span class="v">{{ fmt(d.mining_materials) }}</span></div>
      </template>

      <!-- Trade -->
      <template #trade>
        <div class="kv-row"><span class="k">Market profits</span><span class="v">{{ fmtCr(d.trade_profit) }}</span></div>
        <div class="kv-row" v-if="d.trade_markets">
          <span class="k">Markets visited</span><span class="v">{{ fmt(d.trade_markets) }}</span></div>
        <div class="kv-row" v-if="d.trade_resources">
          <span class="k">Resources traded</span><span class="v">{{ fmt(d.trade_resources) }}</span></div>
        <div class="kv-row" v-if="d.mission_income">
          <span class="k">Mission income</span><span class="v">{{ fmtCr(d.mission_income) }}</span></div>
      </template>

      <!-- PowerPlay -->
      <template #pplay>
        <div class="kv-row" v-if="d.pp_power">
          <span class="k">Power</span><span class="v">{{ d.pp_power }}</span></div>
        <div class="kv-row" v-if="d.pp_rank != null">
          <span class="k">Rank</span><span class="v">{{ d.pp_rank }}</span></div>
        <div class="kv-row">
          <span class="k">Merits total</span><span class="v">{{ fmt(d.pp_merits) }}</span></div>
      </template>

    </TabSet>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TabSet from './TabSet.vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const d = computed(() => props.data);

const tabs = [
  { id: 'summary', label: 'Summary'  },
  { id: 'combat',  label: 'Combat'   },
  { id: 'explore', label: 'Explore'  },
  { id: 'exobio',  label: 'Exobio'   },
  { id: 'mining',  label: 'Mining'   },
  { id: 'trade',   label: 'Trade'    },
  { id: 'pplay',   label: 'PowerPlay'},
];

function fmtCr(n) {
  if (!n) return '—';
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B cr';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M cr';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'k cr';
  return n.toLocaleString() + ' cr';
}
function fmt(n) { return (n != null && n !== 0) ? n.toLocaleString() : '0'; }
function fmtDur(s) {
  if (!s) return '—';
  const h = Math.floor(s / 3600);
  if (h >= 24) return `${Math.floor(h/24)}d ${h%24}h`;
  if (h) return `${h}h ${Math.floor((s%3600)/60)}m`;
  return `${Math.floor(s/60)}m`;
}
</script>

<style scoped>
.kv-row  { display: flex; align-items: baseline; padding: 1px 0; font-size: 12px; gap: 4px; }
.k       { color: var(--text-dim); font-size: 11px; flex: 1; }
.v       { text-align: right; }
.rate    { color: var(--text-dim); font-size: 10px; min-width: 52px; text-align: right; }
.warn    { color: var(--health-warn); }
.dim     { color: var(--text-dim); font-size: 11px; }
.padded  { padding: 8px 0; text-align: center; }
.sec-hdr { color: var(--accent); font-size: 10px; text-transform: uppercase;
           letter-spacing: 0.06em; margin: 5px 0 1px; }
</style>
