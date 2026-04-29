<template>
  <div class="health-bar-outer">
    <div class="health-bar-inner" :class="cls" :style="{ width: clamped + '%' }"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ pct: { type: Number, default: 100 } });
const clamped = computed(() => Math.max(0, Math.min(100, props.pct ?? 0)));
const cls = computed(() => {
  const p = clamped.value;
  if (p > 75)  return 'good';
  if (p >= 25) return 'warn';
  return 'crit';
});
</script>
