<template>
  <div class="panel">
    <div class="panel-header">Engineering</div>
    <!-- 7 tabs matching GTK4 exactly: Raw, Mfg, Enc, Comp, Items, Cons, Data -->
    <TabSet :tabs="tabs" style="flex:1;min-height:0;">
      <template v-for="tab in tabs" :key="tab.id" v-slot:[tab.id]>
        <div class="mat-count-hdr">
          <span class="mat-label">{{ tab.label }}</span>
          <span class="mat-total">{{ total(categoryData[tab.id]) }}</span>
        </div>
        <div v-if="!categoryData[tab.id]?.length" class="dim">No data</div>
        <div v-for="m in categoryData[tab.id]" :key="m.key" class="mat-row">
          <span class="mat-name">{{ m.name }}</span>
          <span class="mat-count">{{ m.count }}</span>
        </div>
      </template>
    </TabSet>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TabSet from './TabSet.vue';

const props = defineProps({
  data: { type: Object, default: () => ({ raw: [], manufactured: [], encoded: [], locker: {} }) }
});
const d = computed(() => props.data);

const tabs = [
  { id: 'raw',          label: 'Raw'   },
  { id: 'manufactured', label: 'Mfg'   },
  { id: 'encoded',      label: 'Enc'   },
  { id: 'components',   label: 'Comp'  },
  { id: 'items',        label: 'Items' },
  { id: 'consumables',  label: 'Cons'  },
  { id: 'data',         label: 'Data'  },
];

const categoryData = computed(() => ({
  raw:          d.value.raw          || [],
  manufactured: d.value.manufactured || [],
  encoded:      d.value.encoded      || [],
  components:   d.value.locker?.components  || [],
  items:        d.value.locker?.items       || [],
  consumables:  d.value.locker?.consumables || [],
  data:         d.value.locker?.data        || [],
}));

function total(arr) {
  return (arr || []).reduce((a, x) => a + (x.count || 0), 0);
}
</script>

<style scoped>
.mat-count-hdr {
  display: flex; align-items: baseline; justify-content: space-between;
  color: var(--accent); font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.05em; margin-bottom: 3px; padding-bottom: 2px;
  border-bottom: 1px solid var(--border);
}
.mat-label { }
.mat-total { color: var(--text-dim); font-weight: normal; }
.mat-row {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 1px 0; font-size: 11px;
}
.mat-row:hover { background: var(--bg-hover); }
.mat-name  { color: var(--text-dim); flex: 1; }
.mat-count { font-variant-numeric: tabular-nums; min-width: 30px; text-align: right; }
.dim       { color: var(--text-muted); font-size: 10px; padding: 4px 0; }
</style>
