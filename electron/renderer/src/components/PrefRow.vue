<template>
  <div class="pref-row">
    <label class="pref-label">
      {{ label }}
      <span v-if="restart" class="restart-tag" title="Requires restart">⚠</span>
    </label>
    <div class="pref-control"><slot /></div>
  </div>
</template>
<script setup>
defineProps({ label: String, restart: Boolean });
</script>
<style scoped>
.pref-row     { display: flex; align-items: center; padding: 3px 0;
                border-bottom: 1px solid var(--border); gap: 8px; }
.pref-label   { flex: 1; color: var(--text-dim); font-size: 11px; }
.pref-control { flex-shrink: 0; }
.restart-tag  { color: var(--health-warn); margin-left: 3px; font-size: 10px; }
</style>
