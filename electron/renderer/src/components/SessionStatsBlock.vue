<template>
  <div class="panel">
    <div class="panel-header">Session</div>

    <TabSet :tabs="tabs" style="flex:1;min-height:0;">
      <template #summary>
        <div v-if="!providers.length && !d.duration" class="dim">Session not started</div>
        <!-- Duration row first — matches GTK4 where Duration is the first Summary grid row -->
        <div v-if="d.duration" class="kv-row">
          <span class="kv-key">Duration</span>
          <span class="kv-val">{{ d.duration }}</span>
        </div>
        <template v-for="prov in providers" :key="prov.provider">
          <div class="sec-hdr">{{ prov.provider }}</div>
          <div v-for="row in prov.rows" :key="row.label" class="kv-row">
            <span class="kv-key">{{ row.label }}</span>
            <span class="kv-val">
              {{ row.value }}
              <span v-if="row.rate" class="rate">{{ row.rate }}</span>
            </span>
          </div>
        </template>
      </template>

      <template v-for="tab in providerTabs" :key="tab.id" v-slot:[tab.id]>
        <template v-for="row in getProviderRows(tab.label)" :key="row.label">
          <div class="kv-row">
            <span class="kv-key">{{ row.label }}</span>
            <span class="kv-val">
              {{ row.value }}
              <span v-if="row.rate" class="rate">{{ row.rate }}</span>
            </span>
          </div>
        </template>
        <div v-if="!getProviderRows(tab.label).length" class="dim">No activity</div>
      </template>
    </TabSet>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TabSet from './TabSet.vue';

const props = defineProps({ data: { type: Object, default: () => ({}) } });
const d = computed(() => props.data);
const providers = computed(() => d.value.providers || []);

// Base tabs + one per provider
const providerTabs = computed(() =>
  providers.value.map((p, i) => ({
    id:    `prov_${i}`,
    label: p.provider,
  }))
);
const tabs = computed(() => [
  { id: 'summary', label: 'Summary' },
  ...providerTabs.value,
]);

function getProviderRows(label) {
  const p = providers.value.find(p => p.provider === label);
  return p?.rows || [];
}
</script>

<style scoped>
.dur     { margin-left: auto; color: var(--text-dim); font-size: 11px; font-weight: normal; }
.sec-hdr { color: var(--accent); font-size: 10px; text-transform: uppercase;
           letter-spacing: 0.06em; margin: 5px 0 2px; }
.dim     { color: var(--text-dim); font-size: 11px; }
.rate    { color: var(--text-dim); font-size: 10px; margin-left: 4px; }
</style>
