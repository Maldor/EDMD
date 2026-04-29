<template>
  <div class="panel-overlay" @click.self="$emit('close')">
    <div class="reports-window">
      <div class="reports-header">
        <span>REPORTS</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="reports-body">
        <!-- Sidebar -->
        <div class="reports-sidebar">
          <button v-for="r in reports" :key="r.key"
                  class="report-btn" :class="{ active: activeReport === r.key }"
                  @click="loadReport(r.key)">
            {{ r.label }}
          </button>
        </div>

        <!-- Content pane -->
        <div class="reports-content">
          <div v-if="!activeReport" class="placeholder">
            Select a report from the sidebar.
          </div>

          <div v-else-if="loading" class="loading">
            <div class="spinner"></div>
            <span>Scanning journals…</span>
          </div>

          <div v-else-if="error" class="error">
            <pre>{{ error }}</pre>
          </div>

          <template v-else>
            <div class="report-title">{{ reportTitle }}</div>
            <div v-if="reportSubtitle" class="report-subtitle">{{ reportSubtitle }}</div>

            <div class="report-body">
              <template v-for="(row, i) in reportRows" :key="i">

                <!-- Section heading -->
                <div v-if="row._type === 'header'" class="rpt-section">
                  {{ row.text }}
                </div>

                <!-- Column headers for tabular sections -->
                <div v-else-if="row._type === 'col_headers'" class="rpt-col-headers">
                  <span v-for="col in row.columns" :key="col" class="rpt-col-hdr">
                    {{ col }}
                  </span>
                </div>

                <!-- Separator between sections -->
                <div v-else-if="row._type === 'sep'" class="rpt-sep"></div>

                <!-- Prose block -->
                <div v-else-if="row._type === 'prose'" class="rpt-prose">
                  {{ row.text }}
                </div>

                <!-- Note -->
                <div v-else-if="row._type === 'note'" class="rpt-note">
                  {{ row.text }}
                </div>

                <!-- Data row -->
                <div v-else class="rpt-row">
                  <span class="rpt-label">{{ row.label }}</span>
                  <span v-if="row.value !== undefined" class="rpt-value">{{ row.value }}</span>
                  <span v-if="row.extra"               class="rpt-extra">{{ row.extra }}</span>
                </div>

              </template>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const emit = defineEmits(['close', 'send']);

const reports = [
  { key: 'career',          label: 'Career Overview'    },
  { key: 'bounties',        label: 'Bounty Breakdown'   },
  { key: 'sessions',        label: 'Session History'    },
  { key: 'hunting_grounds', label: 'Hunting Grounds'    },
  { key: 'rogues',          label: "NPC Rogues' Gallery"},
  { key: 'exploration',     label: 'Exploration Stats'  },
  { key: 'exobiology',      label: 'Exobiology Stats'   },
];

const activeReport  = ref('');
const loading       = ref(false);
const error         = ref('');
const reportTitle   = ref('');
const reportSubtitle= ref('');
const reportRows    = ref([]);

function loadReport(key) {
  activeReport.value   = key;
  loading.value        = true;
  error.value          = '';
  reportRows.value     = [];
  emit('send', { cmd: 'run_report', report: key });
}

function applyReport(data) {
  loading.value         = false;
  error.value           = data.error || '';
  reportTitle.value     = data.title    || '';
  reportSubtitle.value  = data.subtitle || '';
  reportRows.value      = data.rows     || [];
}

defineExpose({ applyReport });
</script>

<style scoped>
.panel-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.reports-window {
  background: var(--bg-panel);
  border: 1px solid var(--border-accent);
  border-radius: 3px;
  width: min(1000px, 94vw);
  height: 82vh;
  display: flex; flex-direction: column;
}
.reports-header {
  background: var(--bg-header);
  color: var(--accent);
  font-weight: bold; font-size: 12px;
  padding: 6px 12px;
  display: flex; align-items: center;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.close-btn {
  margin-left: auto; background: none; border: none;
  color: var(--text-dim); cursor: pointer; font-size: 14px; line-height: 1;
}
.close-btn:hover { color: var(--text); }

.reports-body    { display: flex; flex: 1; overflow: hidden; }
.reports-sidebar {
  width: 156px; flex-shrink: 0;
  background: var(--bg-header);
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 8px 0;
}
.report-btn {
  display: block; width: 100%;
  background: none; border: none;
  border-left: 2px solid transparent;
  color: var(--text-dim); text-align: left;
  padding: 6px 12px; font-size: 11px; font-family: inherit;
  cursor: pointer; line-height: 1.3;
}
.report-btn.active  { color: var(--accent); border-left-color: var(--accent);
                       background: var(--bg-hover); }
.report-btn:hover:not(.active) { color: var(--text); background: var(--bg-hover); }

.reports-content { flex: 1; overflow-y: auto; padding: 12px 16px; }

.placeholder { color: var(--text-muted); font-size: 12px; padding-top: 8px; }
.loading     { display: flex; align-items: center; gap: 12px; color: var(--text-dim); }
.spinner     { width: 20px; height: 20px; border: 2px solid var(--border);
               border-top-color: var(--accent); border-radius: 50%;
               animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { color: var(--health-crit); font-size: 11px; }
.error pre { white-space: pre-wrap; word-break: break-all; }

.report-title    { color: var(--accent); font-weight: bold; font-size: 13px;
                   margin-bottom: 2px; }
.report-subtitle { color: var(--text-dim); font-size: 11px; margin-bottom: 10px; }
.report-body     { margin-top: 4px; }

.rpt-section     { color: var(--accent); font-size: 10px; text-transform: uppercase;
                   letter-spacing: 0.08em; margin: 10px 0 3px;
                   border-bottom: 1px solid var(--border); padding-bottom: 2px; }
.rpt-col-headers { display: flex; gap: 16px; color: var(--text-dim); font-size: 10px;
                   text-transform: uppercase; letter-spacing: 0.05em;
                   padding: 2px 0; border-bottom: 1px solid var(--border);
                   margin-bottom: 2px; }
.rpt-col-hdr     { flex: 1; }
.rpt-sep         { height: 1px; background: var(--border); margin: 6px 0; }
.rpt-prose       { color: var(--text-dim); font-size: 11px; line-height: 1.5;
                   margin: 4px 0; }
.rpt-note        { color: var(--text-muted); font-size: 10px; font-style: italic;
                   margin: 2px 0; }
.rpt-row {
  display: flex; align-items: baseline; gap: 8px;
  padding: 2px 0; border-bottom: 1px solid transparent; font-size: 12px;
}
.rpt-row:hover { background: var(--bg-hover); }
.rpt-label { color: var(--text-dim); flex: 1; font-size: 11px;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rpt-value { white-space: nowrap; }
.rpt-extra { color: var(--text-dim); font-size: 10px; white-space: nowrap; }
</style>
