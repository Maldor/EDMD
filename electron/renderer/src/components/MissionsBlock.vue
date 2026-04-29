<template>
  <div class="panel">
    <div class="panel-header">Mission Stack</div>
    <div class="panel-body">
      <div v-if="!d.has_detail" class="dim">No active missions</div>

      <template v-else>
        <!-- Active count left, reward right — matching GTK4 grid alignment -->
        <div class="mission-grid">
          <span class="col-key">Active</span>
          <span class="col-count">{{ d.n_missions }}/{{ d.full_stack }}</span>
          <span class="col-rew"></span>
        </div>
        <div v-if="d.missions_complete" class="mission-grid">
          <span class="col-key dim">Redirected</span>
          <span class="col-count dim">{{ d.missions_complete }}/{{ d.n_missions }}</span>
          <span class="col-rew"></span>
        </div>

        <div class="sec-hdr">By Source Faction</div>
        <div v-for="f in factions" :key="f.faction" class="mission-grid faction-row">
          <span class="col-key">{{ f.faction }}</span>
          <span class="col-count">{{ f.kill_count }}</span>
          <span class="col-rew">{{ fmtCr(f.reward) }}</span>
        </div>

        <div class="sep-line"></div>

        <!-- Stack height: kills | total credit value — matches GTK4 layout -->
        <div class="mission-grid">
          <span class="col-key dim">Stack height</span>
          <span class="col-count dim">{{ d.stack_height }}</span>
          <span class="col-rew accent">{{ fmtCr(d.total_reward) }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ data: { type: Object, default: () => ({}) } });
const d = computed(() => props.data);
const factions = computed(() => d.value.factions || []);

function fmtCr(n) {
  if (!n) return '';
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  return n.toLocaleString();
}
</script>

<style scoped>
/* Three-column grid: faction name | kill count | reward — all rows share same columns */
.mission-grid {
  display:               grid;
  grid-template-columns: 1fr 40px 60px;
  align-items:           baseline;
  padding:               1px 0;
  font-size:             12px;
  gap:                   4px;
}
.col-key   { white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
             color: var(--text-dim); font-size: 11px; }
.col-count { text-align: right; font-variant-numeric: tabular-nums; }
.col-rew   { text-align: right; font-size: 10px; color: var(--text-dim); }
.accent    { color: var(--accent); font-size: 11px; }

.dim       { color: var(--text-dim) !important; }
.sep-line  { height: 1px; background: var(--border); margin: 3px 0; }

.sec-hdr   { color: var(--accent); font-size: 10px; text-transform: uppercase;
             letter-spacing: 0.06em; margin: 5px 0 2px; }
</style>
