<template>
  <div class="panel">
    <!-- Header: CARGO left, station/gal avg right -->
    <div class="panel-header">
      CARGO
      <span class="mkt-label">{{ marketLabel }}</span>
    </div>
    <div class="panel-body cargo-body">
      <!-- Column headers — 4 columns matching GTK4: name | qty | sell | avg -->
      <div class="col-hdr">
        <span class="c-name">Commodity</span>
        <span class="c-qty">Qty</span>
        <span class="c-sell">{{ hasTarget ? 'Target' : 'Sell' }}</span>
        <span class="c-avg">Avg</span>
      </div>

      <div v-if="d.used === 0" class="dim">Hold empty</div>
      <template v-else-if="d.used > 0">
        <div v-for="item in items" :key="item.key" class="cargo-row"
             :class="{ stolen: item.stolen }">
          <span class="c-name">{{ item.name }}</span>
          <span class="c-qty">{{ item.count }}</span>
          <span class="c-sell dim">{{ fmtCr(item.col2_price) }}</span>
          <span class="c-avg dim">{{ fmtCr(item.col3_price) }}</span>
        </div>
        <div class="cargo-sep"></div>
        <!-- Total row: "Total" in name, "N/MT" in qty, totals in price cols -->
        <div class="cargo-row total-row">
          <span class="c-name">Total</span>
          <span class="c-qty total-qty">{{ d.used || 0 }}&thinsp;T</span>
          <span class="c-sell">{{ fmtCr(totalCol2) }}</span>
          <span class="c-avg dim">{{ fmtCr(totalCol3) }}</span>
        </div>
      </template>

      <!-- Station search — clears back to galactic average -->
      <div class="search-area">
        <SpanshSearch
          ref="stationSearch"
          placeholder="Select target market…"
          search-cmd="search_market"
          :initial-text="''"
          @pick="onStationPick"
          @clear="onStationClear"
          @send="$emit('send', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import SpanshSearch from './SpanshSearch.vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const emit  = defineEmits(['send']);
const d = computed(() => props.data);
const stationSearch = ref(null);

const items     = computed(() => d.value.items || []);
const hasTarget = computed(() => !!d.value.has_target);

// Header right label:
// - When target set: show station name
// - Default: "GALACTIC AVERAGE"
const marketLabel = computed(() => {
  if (d.value.target_market_name) return d.value.target_market_name;
  return 'GALACTIC AVERAGE';
});

const totalCol2 = computed(() =>
  items.value.reduce((s, i) => s + (i.col2_price || 0) * i.count, 0)
);
const totalCol3 = computed(() =>
  items.value.reduce((s, i) => s + (i.col3_price || 0) * i.count, 0)
);

function fmtCr(n) {
  if (!n) return '—';
  if (n >= 1e9) return (n/1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return Math.round(n/1e3) + 'K';
  return n.toLocaleString();
}

function onStationPick(result) {
  emit('send', {
    cmd:          'set_target_market',
    station_name: result.name,
    system_name:  result.system || '',
    record:       result,
  });
  stationSearch.value?.reset();
}
function onStationClear() {
  // Clear target → back to galactic average
  emit('send', { cmd: 'clear_target_market' });
}
</script>

<style scoped>
.cargo-body { padding: 4px 8px 6px; display: flex; flex-direction: column; gap: 1px; }

/* Header right label */
.mkt-label  { margin-left: auto; color: var(--text-dim); font-size: 10px;
              font-weight: normal; text-transform: uppercase; letter-spacing: 0.04em; }

/* 4-column grid: name stretches, qty fixed, sell fixed, avg fixed */
.col-hdr, .cargo-row {
  display:               grid;
  grid-template-columns: 1fr 40px 56px 56px;
  align-items:           baseline;
  font-size:             11px;
}
.col-hdr    { color: var(--text-dim); font-size: 10px; text-transform: uppercase;
              letter-spacing: 0.04em; padding-bottom: 2px;
              border-bottom: 1px solid var(--border); }
.cargo-row:hover          { background: var(--bg-hover); }
.cargo-row.stolen .c-name { color: var(--health-warn); }
.total-row .c-name        { font-weight: bold; }

/* Column alignment */
.c-name  { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 4px; }
.c-qty   { text-align: right; font-variant-numeric: tabular-nums; padding-right: 8px; }
.c-sell  { text-align: right; font-variant-numeric: tabular-nums; }
.c-avg   { text-align: right; font-variant-numeric: tabular-nums; }

/* Total qty: right-aligned with 1 space gap before T */
.total-qty { color: var(--text); padding-right: 0; text-align: right; }

.dim        { color: var(--text-dim); }
.cargo-sep  { height: 1px; background: var(--border); margin: 2px 0; }
.search-area{ margin-top: 5px; border-top: 1px solid var(--border); padding-top: 5px; }
</style>
