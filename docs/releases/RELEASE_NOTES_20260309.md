# EDMD Release Notes

---

## 20260309

**Elite Dangerous Monitor Daemon — EDMD**

---

### Bug Fix — Kill Counter: Kills Required Scrapped

**Background:** The kills-remaining display that tracked outstanding kill quota across massacre missions was removed entirely. Deep investigation against real journal data (including cross-referencing the EDMC-Massacre plugin source and FIFO kill credit mechanics) established that the journal does not provide enough information to accurately attribute kills to specific missions when multiple missions share the same target faction. The `MissionRedirected` event is the only reliable signal that a mission's quota has been met — there is no in-journal mechanism to track incremental credit.

All kill-tracking infrastructure has been removed: `target_kill_totals`, `target_kills_credited`, `recalc_target_kill_totals()`, and associated GUI rows. The mission panel now shows stack value and completion count (missions redirected / total active), which are accurate.

---

### Bug Fix — Journal Switch: Stale Mission State After Client Restart

When the Elite Dangerous client was restarted, EDMD detected the new journal file but carried stale mission state from the previous session into it. Because `state.missions` was already `True`, the `Missions` bulk event in the new journal was skipped and `bootstrap_missions()` was bypassed — leaving old missions mixed in with the new stack, or preventing the new session's stack from being recognised at all.

**Fix:** The `LoadGame` event handler now calls `state.reset_missions()` as its first action, clearing all mission fields before the new session's events are processed. A new `MonitorState.reset_missions()` method encapsulates this so the same path can be used anywhere a clean mission slate is required.

---

### Bug Fix — SLF: `FighterRebuilt` Incorrectly Clobbered Deployed State

When a destroyed fighter was rebuilt in the hangar, the `FighterRebuilt` event handler was unconditionally setting `slf_deployed = False` and `slf_docked = False`. If the commander had immediately launched a replacement fighter before EDMD processed the event, the panel would flip to showing the SLF as neither deployed nor docked — an impossible state — until the next event corrected it.

**Fix:** `FighterRebuilt` now only resets SLF state if the SLF is not currently deployed. If `slf_deployed` is already `True` when the event arrives, the rebuild is acknowledged silently and state is left intact.

---

### Bug Fix — Periodic Summary: Redundant Stack Value on Kill Lines

The periodic session summary was appending the full mission stack value to each faction kill line, duplicating information already present on the `Missions` line immediately above it.

Before:
```
- Missions: 386.32M stack (18/20 complete, 2 remaining)
- Kills:    147 remaining vs Bhutatani Partnership | 386.32M stack
```

After:
```
- Missions: 386.32M stack (18/20 complete, 2 remaining)
- Kills:    147 remaining vs Bhutatani Partnership
```

---

### Major Refactor — Package Structure

EDMD has been restructured from a two-file monolith (`edmd.py` ~3000 lines, `edmd_gui.py` ~1000 lines) into a properly packaged codebase. All user-facing behaviour is preserved.

**New layout:**

```
edmd.py       — entry point only (~230 lines)
core/         — state, config, emit, journal loop, plugin loader, shared API
builtins/     — five built-in data plugins
plugins/      — user plugin directory (empty by default, gitignored)
gui/          — GTK4 interface package
```

**`core/` modules:**

| Module | Contents |
|--------|----------|
| `state.py` | Constants, `SessionData`, `MonitorState`, session persistence |
| `config.py` | `ConfigManager`, hot-reload, profile resolution |
| `emit.py` | `Terminal`, `Emitter`, Discord webhook, format helpers |
| `journal.py` | Journal loop, event dispatch, bootstrap functions |
| `core_api.py` | `CoreAPI` — shared interface for plugins and GUI |
| `plugin_loader.py` | `BasePlugin`, `PluginLoader` |

**`builtins/` plugins:**

| Plugin | Tracks |
|--------|--------|
| `commander` | Pilot, ship, location, powerplay, hull/shields |
| `missions` | Massacre mission stack, completion state |
| `session_stats` | Kills, bounties, merits, rates |
| `crew_slf` | NPC crew, SLF, fighter bay |
| `alerts` | Alert queue with opacity fade |

**`gui/` package:**

| File | Contents |
|------|----------|
| `helpers.py` | PP rank math, theme loader, widget factories |
| `block_base.py` | `BlockWidget` base class |
| `blocks/*.py` | One block widget per builtin |
| `app.py` | `EdmdWindow`, `EdmdApp` |

`edmd_gui.py` has been retired. `edmd.py` now imports directly from `gui.app`.

---

### Plugin System

EDMD now has a plugin interface. Plugins are Python classes that subscribe to journal events and provide data to the GUI. Drop a plugin into `plugins/<name>/plugin.py` and it loads automatically alongside the five builtins.

See the **Plugin Development** section in README.md for the full interface reference.

---

### Theme Template — Moved

The custom theme starter file has moved from `themes/custom/my-theme.css` (gitignored) to `themes/custom-template.css` (tracked). This ensures the template is always available after a pull without risking overwriting themes you have created in `themes/custom/`.

**Migration:** If you had customised `themes/custom/my-theme.css`, it is unaffected — your `themes/custom/` directory remains gitignored. Simply update your config to reference the new template path if you were using it directly:

```toml
[GUI]
Theme = "custom/mytheme"   # your themes/custom/ files are unchanged
```

To start a new custom theme from the template:
```bash
cp themes/custom-template.css themes/custom/mytheme.css
```

---

### Upgrading from 20260308b

No config changes required. Run `edmd.py --upgrade` or use the Upgrade button in the GUI.

The `plugins/` directory is gitignored — any plugins you have placed there will not be affected by the upgrade.

---

### Known Limitations (unchanged)

- SLF shield state is not tracked — the game does not expose this via journal or `Status.json`
- GTK4 GUI is Linux-only; Windows users have terminal and Discord output
- Theme changes require a restart (no hot-reload for CSS)
