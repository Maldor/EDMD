<template>
  <!-- Hidden entirely when no active crew, matching GTK4 behaviour -->
  <div v-if="d.has_crew" class="panel">
    <!-- Header: CREW: NAME + SLF type (right) + rank + variant -->
    <div class="panel-header crew-hdr">
      <div class="hdr-left">
        <div class="crew-name">{{ crewTitle }}</div>
        <div v-if="d.crew_rank != null" class="crew-rank">{{ rankStr }}</div>
      </div>
      <div class="hdr-right">
        <div class="slf-type">{{ d.slf_type || '' }}</div>
        <div v-if="d.slf_variant" class="slf-variant">{{ d.slf_variant }}</div>
      </div>
    </div>

    <div class="panel-body">
      <div class="grid">
        <!-- SLF status first — matching GTK4/TUI order: SLF, Hired, Active, Paid -->
        <template v-if="d.has_fighter_bay">
          <span class="k">SLF</span>
          <span class="v" :class="slfCls">{{ slfStatus }}</span>
        </template>

        <span class="k">Hired</span>
        <span class="v">{{ d.crew_hire_time || '—' }}</span>
        <span class="k">Active</span>
        <span class="v">{{ d.crew_active_str || '—' }}</span>
        <span class="k">Paid</span>
        <span class="v">{{ paidStr }}</span>
      </div>
    </div>
  </div>
  <!-- Fallback: show empty crew panel -->
  <div v-else class="panel">
    <div class="panel-header">Crew</div>
    <div class="panel-body dim">No NPC crew</div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const d = computed(() => props.data);

const PP_RANKS = [
  'Harmless','Mostly Harmless','Novice','Competent','Expert',
  'Master','Dangerous','Deadly','Elite',
  'Elite I','Elite II','Elite III','Elite IV','Elite V',
];

const crewTitle = computed(() => {
  const name = d.value.crew_name || 'NPC';
  if (d.value.cmdr_in_slf) return `CREW: ${name}  [Flying ${d.value.pilot_ship || 'Ship'}]`;
  return `CREW: ${name}`;
});

const rankStr = computed(() => {
  const r = d.value.crew_rank;
  if (r == null) return '';
  const name = PP_RANKS[r] || `Rank ${r}`;
  return `Combat Rank: ${name}`;
});

const paidStr = computed(() => {
  const paid = d.value.crew_total_paid;
  if (!paid) return '—';
  const prefix = d.value.crew_paid_complete ? '' : '≥ ';
  return `${prefix}${fmtCr(paid)}`;
});

const slfStatus = computed(() => {
  const {slf_deployed, slf_docked, slf_hull, cmdr_in_slf,
         slf_stock_total, slf_destroyed_count} = d.value;
  if (cmdr_in_slf) return `CMDR Aboard  |  Hull ${slf_hull ?? '—'}%`;
  if (slf_docked)  return 'SLF Docked';
  if (slf_deployed) return `Hull ${slf_hull ?? '—'}%`;
  const allSpent = slf_stock_total > 0 && slf_destroyed_count >= slf_stock_total;
  if (allSpent) return 'All Spent';
  return 'Destroyed';
});

const slfCls = computed(() => {
  const h = d.value.slf_hull ?? 100;
  if (d.value.slf_deployed) {
    if (h > 75) return 'good';
    if (h >= 25) return 'warn';
    return 'crit';
  }
  return '';
});

function fmtCr(n) {
  if (!n) return '—';
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B cr';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M cr';
  return n.toLocaleString() + ' cr';
}
</script>

<style scoped>
.crew-hdr  { display: flex; align-items: flex-start; padding: 4px 6px; }
.hdr-left  { flex: 1; }
.hdr-right { text-align: right; flex-shrink: 0; }
.crew-name  { font-weight: bold; color: var(--accent); font-size: 12px; line-height: 1.3; }
.crew-rank  { font-size: 10px; color: var(--accent);   line-height: 1.2; }
.slf-type   { font-size: 12px; color: var(--accent); font-weight: bold; line-height: 1.3; }
.slf-variant { font-size: 10px; color: var(--accent);   line-height: 1.2; }

.grid {
  display:               grid;
  grid-template-columns: auto 1fr;
  column-gap:            8px;
  row-gap:               2px;
  font-size:             12px;
}
.k    { color: var(--text-dim); font-size: 11px; white-space: nowrap; align-self: center; }
.v    { text-align: right; align-self: center; }
.good { color: var(--health-good); }
.warn { color: var(--health-warn); }
.crit { color: var(--health-crit); }
.dim  { color: var(--text-dim); font-size: 11px; }
</style>
