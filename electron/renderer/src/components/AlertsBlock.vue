<template>
  <div class="panel">
    <div class="panel-header">Alerts</div>
    <div class="panel-body alerts-body">
      <div v-if="!alerts.length" class="no-alerts">No recent alerts</div>
      <div v-for="(a, i) in alerts" :key="i"
           class="alert-entry" :class="{ faded: opacity(a) < 0.7 }"
           :style="{ opacity: opacity(a) }">
        {{ a.emoji }}  {{ a.text }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ data: { type: Object, default: () => ({ alerts: [] }) } });
const alerts = computed(() => props.data.alerts || []);

function opacity(a) {
  const age = (performance.now() / 1000) - a.mono_time;
  if (age < 60)  return 1.0;
  if (age > 90)  return 0.4;
  return 1.0 - (age - 60) / 30 * 0.6;
}
</script>

<style scoped>
.alerts-body { padding: 4px; }
.no-alerts   { color: var(--text-muted); font-size: 11px; padding: 4px; }
</style>
