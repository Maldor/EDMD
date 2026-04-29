<template>
  <div class="spansh-search" ref="root">
    <div class="search-row">
      <input
        ref="inp"
        class="search-input"
        :placeholder="placeholder"
        :value="inputText"
        @input="onInput"
        @keydown.enter.prevent="onEnter"
        @keydown.escape.prevent="close"
        @focus="onFocus"
      />
      <button v-if="inputText" class="clear-btn" @click="onClear" tabindex="-1">✕</button>
    </div>

    <!-- Dropdown results -->
    <div v-if="open && results.length" class="results-dropdown">
      <button
        v-for="r in results" :key="r.name + r.system"
        class="result-row"
        @mousedown.prevent="onPick(r)"
      >
        <span class="result-icon">{{ r.is_station ? '🚉' : '⭐' }}</span>
        <span class="result-name">{{ r.name }}</span>
        <span v-if="r.system && r.system !== r.name" class="result-sys">{{ r.system }}</span>
      </button>
    </div>

    <div v-if="open && !results.length && searching" class="results-dropdown">
      <div class="result-dim">Searching…</div>
    </div>
    <div v-if="open && !results.length && !searching && inputText.length >= 3" class="results-dropdown">
      <div class="result-dim">No results found</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  placeholder: { type: String, default: 'Search…' },
  searchCmd:   { type: String, required: true },   // 'search_home' | 'search_market'
  initialText: { type: String, default: '' },
});
const emit = defineEmits(['pick', 'clear', 'send']);

const inputText = ref(props.initialText || '');
const results   = ref([]);
const open      = ref(false);
const searching = ref(false);
let debounce    = null;

function onInput(e) {
  inputText.value = e.target.value;
  results.value   = [];
  clearTimeout(debounce);
  if (inputText.value.length < 3) { open.value = false; return; }
  searching.value = true;
  open.value      = true;
  debounce = setTimeout(() => doSearch(inputText.value), 400);
}

function doSearch(q) {
  emit('send', {
    cmd: props.searchCmd,
    query: q,
    _callback: (data) => {
      searching.value = false;
      results.value   = data.results || [];
      open.value      = results.value.length > 0 || inputText.value.length >= 3;
    },
  });
}

function onEnter() {
  if (results.value.length) { onPick(results.value[0]); return; }
  if (inputText.value.length >= 3) doSearch(inputText.value);
}

function onPick(r) {
  inputText.value = r.name;
  open.value      = false;
  results.value   = [];
  emit('pick', r);
  // Surrender focus so typing goes back to the window, not the search field
  inp.value?.blur();
}

function onClear() {
  inputText.value = '';
  results.value   = [];
  open.value      = false;
  emit('clear');
}

function onFocus() { if (results.value.length) open.value = true; }
function close() { open.value = false; }

// reset(): clear the field visually without emitting 'clear' (used after pick)
function reset() {
  inputText.value = '';
  results.value   = [];
  open.value      = false;
  // No emit — this is an internal visual reset, not a user-initiated clear
}

// Allow parent to update inputText
watch(() => props.initialText, v => { inputText.value = v || ''; });

// Expose both:
//   clear() — user-initiated clear (emits 'clear' so parent can clear_home / clear_target)
//   reset() — visual reset after pick (does NOT emit; pick already handled the action)
defineExpose({ clear: onClear, reset });
</script>

<style scoped>
.spansh-search { position: relative; width: 100%; }
.search-row    { display: flex; align-items: center; gap: 2px; }
.search-input  {
  flex:        1; min-width: 0;
  background:  var(--bg-input); border: 1px solid var(--border);
  color:       var(--text); font-family: inherit; font-size: 11px;
  padding:     2px 6px; border-radius: 2px; outline: none;
}
.search-input:focus { border-color: var(--accent); }
.clear-btn {
  background: none; border: none; color: var(--text-dim);
  cursor: pointer; font-size: 12px; padding: 0 4px; flex-shrink: 0;
}
.clear-btn:hover { color: var(--text); }

.results-dropdown {
  position:   absolute; left: 0; right: 0; top: calc(100% + 2px);
  background: var(--bg-panel); border: 1px solid var(--border-accent);
  border-radius: 2px; z-index: 50; max-height: 200px; overflow-y: auto;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.result-row {
  display:     flex; align-items: baseline; gap: 6px; width: 100%;
  background:  none; border: none; border-bottom: 1px solid var(--border);
  color:       var(--text); font-family: inherit; font-size: 11px;
  padding:     4px 8px; text-align: left; cursor: pointer;
}
.result-row:last-child  { border-bottom: none; }
.result-row:hover       { background: var(--bg-hover); }
.result-icon { flex-shrink: 0; }
.result-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.result-sys  { color: var(--text-dim); font-size: 10px; white-space: nowrap; }
.result-dim  { color: var(--text-dim); font-size: 11px; padding: 6px 8px; }
</style>
