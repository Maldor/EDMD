<template>
  <select class="pref-select" :value="modelValue ? 'true' : 'false'"
          @change="$emit('update:modelValue', $event.target.value === 'true'); $emit('change', $event.target.value === 'true')">
    <option value="false">Off</option>
    <option value="true">On</option>
  </select>
</template>
<script setup>
defineProps({ modelValue: Boolean });
defineEmits(['update:modelValue', 'change']);
</script>
<style scoped>
.pref-select { background: var(--bg-input); border: 1px solid var(--border);
               color: var(--text); font-family: inherit; font-size: 12px;
               padding: 2px 6px; border-radius: 2px; width: 72px; }
</style>
