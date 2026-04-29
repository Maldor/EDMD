<template>
  <div class="tabset">
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: active === tab.id }"
        @click="active = tab.id"
      >{{ tab.label }}</button>
    </div>
    <div class="tab-body">
      <slot :name="active" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  tabs:    { type: Array,  required: true },  // [{ id, label }]
  initial: { type: String, default: null  },
});

const active = ref(props.initial || (props.tabs[0]?.id ?? ''));

// If tabs change (e.g. CAPI arrives), stay on current tab if it still exists
watch(() => props.tabs, (newTabs) => {
  if (!newTabs.find(t => t.id === active.value)) {
    active.value = newTabs[0]?.id ?? '';
  }
});
</script>

<style scoped>
.tabset   { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.tab-bar  {
  display:    flex;
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.tab-bar::-webkit-scrollbar { display: none; }
.tab-btn {
  background: none; border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  cursor: pointer;
  font-family: inherit; font-size: 10px;
  padding: 4px 9px;
  white-space: nowrap;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.tab-btn.active   { color: var(--accent); border-bottom-color: var(--accent); }
.tab-btn:hover:not(.active) { color: var(--text); }
.tab-body { flex: 1; overflow-y: auto; padding: var(--panel-pad); min-height: 0; }
</style>
