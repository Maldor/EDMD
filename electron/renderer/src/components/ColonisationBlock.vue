<template>
  <div class="panel">
    <div class="panel-header">Colonisation</div>
    <div class="panel-body colon-body">

      <div v-if="!sites.length" class="dim">
        No construction sites tracked.<br>Dock at a depot to begin.
      </div>

      <!-- Active sites grouped by system -->
      <template v-for="grp in systemGroups" :key="grp.system">
        <!-- System group header -->
        <div class="sys-hdr" @click="toggleSys(grp.system)"
             role="button" tabindex="0"
             @keydown.enter="toggleSys(grp.system)"
             @keydown.space.prevent="toggleSys(grp.system)">
          <span class="toggle-arrow">{{ isSysExpanded(grp.system) ? '▼' : '▶' }}</span>
          <span class="sys-name">{{ grp.system }}</span>
        </div>

        <template v-if="isSysExpanded(grp.system)">
          <template v-for="site in grp.sites" :key="site.market_id">
            <!-- Site header -->
            <div class="site-hdr" :class="{ current: isCurrent(site) }"
                 @click="toggleSite(site.market_id)" role="button" tabindex="0"
                 @keydown.enter="toggleSite(site.market_id)"
                 @keydown.space.prevent="toggleSite(site.market_id)">
              <span class="toggle-arrow">{{ isSiteExpanded(site.market_id) ? '▼' : '▶' }}</span>
              <span v-if="isCurrent(site)" class="cur-arrow">▶ </span>
              <span class="site-name">{{ site.station_name || site.system }}</span>
              <span class="site-pct">{{ site.progress_pct }}%</span>
            </div>

            <template v-if="isSiteExpanded(site.market_id)">
              <div v-if="!site.resources.length" class="dim indent2">
                (dock to load requirements)
              </div>
              <div v-else-if="allDelivered(site)" class="delivered indent2">
                All resources delivered!
              </div>
              <template v-else>
                <div v-for="res in remaining(site)" :key="res.name"
                     class="res-row" :class="resClass(res)">
                  <span class="res-name">{{ res.name }}</span>
                  <span class="res-val">{{ neededStr(res) }}</span>
                </div>
                <div class="res-row total-row">
                  <span class="res-name dim">Total remaining</span>
                  <span class="res-val total-val">{{ totalRemaining(site).toLocaleString() }} t</span>
                </div>
              </template>
            </template>
          </template>
        </template>
      </template>

      <!-- Completed sites -->
      <div v-for="site in done" :key="'done-' + site.market_id" class="site-done">
        ✓ {{ site.station_name || site.system }} — complete
      </div>

      <!-- Failed sites -->
      <div v-for="site in failed" :key="'fail-' + site.market_id" class="site-failed">
        ✗ {{ site.station_name || site.system }} — failed
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue';

const props = defineProps({ data: { type: Object, default: () => ({ projects: [], docked: false }) } });
const d = computed(() => props.data);

const sites  = computed(() => d.value.projects || []);
const active = computed(() => sites.value.filter(s => !s.complete && !s.failed));
const done   = computed(() => sites.value.filter(s => s.complete));
const failed = computed(() => sites.value.filter(s => s.failed));

// Group active sites by system name, preserving encounter order
const systemGroups = computed(() => {
  const order = [];
  const map = {};
  for (const site of active.value) {
    const sys = site.system || 'Unknown';
    if (!map[sys]) { map[sys] = []; order.push(sys); }
    map[sys].push(site);
  }
  return order.map(sys => ({ system: sys, sites: map[sys] }));
});

// System-level collapse state
const expandedSys  = reactive({});
// Site-level collapse state
const expandedSite = reactive({});

function isSysExpanded(sys)    { return sys  in expandedSys  ? expandedSys[sys]        : true; }
function isSiteExpanded(mid)   { return mid  in expandedSite ? expandedSite[mid]       : true; }

function toggleSys(sys)  { expandedSys[sys]  = !isSysExpanded(sys);  }
function toggleSite(mid) { expandedSite[mid] = !isSiteExpanded(mid); }

function isCurrent(site) { return !!site.is_current; }

function remaining(site) { return (site.resources || []).filter(r => r.remaining > 0); }

function allDelivered(site) {
  return remaining(site).length === 0 && (site.resources || []).length > 0;
}

function totalRemaining(site) {
  return (site.resources || []).reduce((sum, r) => sum + (r.remaining || 0), 0);
}

function neededStr(res) {
  const n = res.remaining || 0;
  let s = `${n.toLocaleString()} needed`;
  const ic = res.in_cargo || 0;
  if (ic > 0) s += ` (${Math.min(ic, n).toLocaleString()} in hold)`;
  return s;
}

function resClass(res) {
  const ic = res.in_cargo || 0;
  const n  = res.remaining || 0;
  if (ic >= n) return 'res-ready';
  if (ic > 0)  return 'res-partial';
  return '';
}
</script>

<style scoped>
.colon-body  { padding: 4px 8px 6px; display: flex; flex-direction: column; gap: 1px; overflow-y: auto; }
.dim         { color: var(--text-dim); font-size: 11px; }

/* System group header */
.sys-hdr     { display: flex; align-items: baseline; gap: 4px;
               margin-top: 6px; font-size: 11px; font-weight: 600;
               cursor: pointer; user-select: none; border-radius: 2px; }
.sys-hdr:first-child { margin-top: 0; }
.sys-hdr:hover { background: var(--bg-hover); }
.sys-name    { flex: 1; color: var(--text); white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }

/* Site header — indented under system */
.site-hdr    { display: flex; align-items: baseline; gap: 4px;
               margin-top: 2px; margin-bottom: 1px; padding-left: 10px;
               font-size: 11px; cursor: pointer; user-select: none; border-radius: 2px; }
.site-hdr:hover { background: var(--bg-hover); }
.site-hdr.current .site-name { font-weight: bold; }
.cur-arrow   { color: var(--accent); flex-shrink: 0; }
.site-name   { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
               color: var(--accent); font-weight: 500; }
.site-pct    { color: var(--text-dim); font-size: 10px; flex-shrink: 0; }

.toggle-arrow { color: var(--text-dim); font-size: 9px; flex-shrink: 0; width: 10px; }

/* Resource rows — indented under site */
.res-row     { display: flex; align-items: baseline; font-size: 11px;
               padding: 0 0 0 26px; gap: 4px; }
.res-name    { flex: 1; color: var(--text-dim); white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }
.res-val     { text-align: right; flex-shrink: 0; font-size: 10px; }
.res-ready   .res-val { color: var(--health-good); }
.res-partial .res-val { color: var(--health-warn); }

.indent2     { padding-left: 26px; font-size: 11px; }

.total-row   { font-size: 10px; margin-top: 4px; border-top: 1px solid var(--border); padding-top: 2px; }
.total-val   { color: var(--text); font-size: 10px; }

.delivered   { color: var(--health-good); font-size: 11px; }
.site-done   { color: var(--health-good); font-size: 11px; margin-top: 2px; }
.site-failed { color: var(--health-crit); font-size: 11px; margin-top: 2px; }
</style>
