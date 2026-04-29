# EDMD Release Notes

---

## 20260319

**Elite Dangerous Monitor Daemon — EDMD**

Major architectural release. EDMD is no longer purely an AFK combat monitor —
it is now a full gaming session dashboard tracking all activity types. Adds
eight activity-tracking plugins, a redesigned tabbed Session Stats block,
a 15-minute session continuity model, and a full UI polish pass.

---

### Architecture — Activity Plugin System

Session tracking is now split across dedicated activity plugins. Each plugin
tracks one type of in-game activity, registers itself with the Session Stats
block as a data provider, and contributes rows to both the Summary tab and
its own detail tab.

| Plugin | Tracks |
|--------|--------|
| `activity_combat` | Kills, bounties, bonds, deaths, fighter losses, faction/ship tally |
| `activity_trade` | Market profit, with mined-cargo vs bought-and-resold differentiation |
| `activity_mining` | Tonnes refined, asteroids prospected, material breakdown |
| `activity_exploration` | FSD jumps, distance, bodies scanned, first discoveries, cartography value |
| `activity_missions` | Mission completions, credits, failures, type breakdown |
| `activity_exobiology` | Organic samples analysed, species tally, credits earned |
| `activity_odyssey` | On-foot deployments (scaffold — expands as Frontier adds events) |
| `activity_powerplay` | Merits earned across **all** PP activities (not just kills), rank tracking |

Plugins implement `ActivityProviderMixin` and call `core.register_session_provider(self)`
in `on_load()`. Session Stats calls `provider.get_summary_rows()` for the
Summary tab and `provider.get_tab_rows()` for detail tabs. Tabs appear and
disappear automatically as activity accumulates — a pure combat session shows
only the Combat tab; a mixed session shows every relevant tab.

Enable or disable individual activity types via Settings → Plugins.

---

### Architecture — Session Boundary Model

Session continuity is now driven by journal boundaries rather than
`SupercruiseDestinationDrop` events.

- **Session start**: first `LoadGame` event
- **Session continues**: next `LoadGame` fires within 15 minutes of the
  previous `Shutdown` — the same session continues, counters carry over
- **New session**: `LoadGame` fires more than 15 minutes after `Shutdown` —
  all activity counters reset, session clock restarts

The 15-minute threshold reflects the boundary between a short break (still
your session) and a real departure (new session). The previous model reset
counters on every RES/warzone drop, which discarded activity from earlier in
the same play session.

---

### Feature — Session Stats Block: Tabbed Layout

The Session Stats block is rebuilt as a dynamic tabbed panel:

- **Summary** tab (always visible): Duration + the most relevant rows from
  every active provider — kills/hr, bounties/hr, trade profit/hr, distance
  jumped, missions completed, samples analysed, deaths, merits/hr
- **Activity tabs**: one per provider with non-zero activity, sorted
  alphabetically — Combat, Exobiology, Exploration, Mining, Missions,
  Odyssey, PowerPlay, Trade
- Tabs appear when the first event of that type fires; they disappear if the
  session resets with no activity

---

### Removal — Mode Plugin

`builtins/mode/` and `gui/blocks/mode.py` are removed. The manual activity
mode selector has been replaced by automatic activity detection — the Session
Stats block shows what you are actually doing, inferred from journal events.

The no-kill inactivity timeout (formerly `QuitOnNoKillsMinutes` in mode) is
now owned by `activity_combat`.

**Files to delete from the repo:**
- `builtins/mode/__init__.py`
- `builtins/mode/plugin.py`
- `gui/blocks/mode.py`

---

### Fix — Menu Popovers Dismiss on Action

Clicking any menu item (Preferences, Plugins, Reports, Documentation, About)
now dismisses the menu popover immediately before opening the target window.
Previously the popover remained open behind the new window, requiring an
extra click to dismiss it.

---

### Feature — Plugins Dialog Redesigned

Settings → Plugins now shows plugins grouped into sections:

- **Core** — commander, alerts, crew_slf, cargo, engineering, assets, missions, session_stats
- **Activity Tracking** — all `activity_*` plugins with one-line descriptions
- **Data Contributions** — eddn, edsm, edastro, inara
- **Third-party Plugins** — user-installed plugins

Each plugin shows its display name, version, description, and an enable/disable
toggle. Section headers show the plugin count. The dialog is scrollable.

All builtins now have `PLUGIN_DESCRIPTION` set.

---

### Default Grid Layout Updated

Session Stats height increased from 10 to 18 rows to accommodate the tab bar
and multiple content rows. Cargo and engineering shifted down accordingly.

| Block | Col | Row | W | H | Change |
|-------|-----|-----|---|---|--------|
| commander | 0 | 0 | 8 | 14 | — |
| session_stats | 8 | 0 | 8 | **18** | **+8** |
| crew_slf | 16 | 0 | 8 | 12 | — |
| missions | 0 | 14 | 8 | 9 | — |
| cargo | 8 | **18** | 8 | 10 | **row +3** |
| engineering | 8 | **28** | 8 | 10 | **row +3** |
| alerts | 0 | 23 | 8 | 10 | — |
| assets | 16 | 12 | 8 | 25 | — |

---

### Upgrading

Delete `~/.local/share/EDMD/layout.json` to apply the updated default grid.

Delete the following files from your EDMD installation:
- `builtins/mode/__init__.py`
- `builtins/mode/plugin.py`
- `gui/blocks/mode.py`

No `config.toml` changes required.

---

### Known Limitations

- `activity_odyssey` is a scaffold — on-foot kills have no dedicated journal
  event yet. The plugin will expand as Frontier adds Odyssey data.
- Session continuity across relaunches requires `Shutdown` events in the
  journal. If the game crashes rather than closing cleanly, the next launch
  is treated as a new session regardless of elapsed time.
- Mining income attribution: commodities are classified as mined when
  `MiningRefined` fired for that commodity type this session AND the average
  cost paid is zero. Edge cases (e.g. buying mined commodities from another
  player) may misclassify.
