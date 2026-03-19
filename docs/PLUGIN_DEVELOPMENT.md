# EDMD Plugin Development Guide

EDMD supports user-written plugins. Drop a directory containing a `plugin.py`
into `plugins/<name>/` and it loads automatically on startup.

---

## Quick start

```
plugins/
  myplugin/
    __init__.py   (empty)
    plugin.py
```

`plugin.py` must define exactly one class that subclasses `BasePlugin`:

```python
from core.plugin_loader import BasePlugin

class MyPlugin(BasePlugin):
    PLUGIN_NAME    = "myplugin"
    PLUGIN_DISPLAY = "My Plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Does something useful."

    SUBSCRIBED_EVENTS = ["Bounty", "FSDJump"]

    def on_load(self, core) -> None:
        super().on_load(core)
        # core is a CoreAPI instance — store it for later use
        # Optionally register a GUI dashboard block:
        # core.register_block(self, priority=50)

    def on_event(self, event: dict, state) -> None:
        ev = event.get("event")
        logtime = event.get("_logtime")   # datetime | None
        if ev == "Bounty":
            value = event.get("TotalReward", 0)
            # ... do something
```

---

## Plugin metadata

| Attribute | Required | Description |
|-----------|----------|-------------|
| `PLUGIN_NAME` | ✅ | Unique snake_case identifier |
| `PLUGIN_DISPLAY` | ✅ | Human-readable name shown in the Plugins menu |
| `PLUGIN_VERSION` | ✅ | Semantic version string |
| `PLUGIN_DESCRIPTION` | recommended | One-line description shown in Plugins dialog |
| `SUBSCRIBED_EVENTS` | ✅ | List of journal event names to receive |
| `PLUGIN_DEFAULT_ENABLED` | optional | `True` (default) — set `False` to ship disabled |
| `DEFAULT_COL/ROW/WIDTH/HEIGHT` | optional | Default dashboard grid position if registering a block |

---

## The `core` object (`CoreAPI`)

Every plugin receives a `CoreAPI` instance in `on_load()`. Store it as
`self.core` (done automatically by `super().on_load(core)`).

### `core.data` — the unified data provider

**This is the primary API for reading game state.** Do not read `core.state`
fields directly — use `core.data` instead.

```python
# Ship vitals
core.data.ship.hull()              # int — hull integrity pct (CAPI > journal)
core.data.ship.shields()           # bool — shields up
core.data.ship.shields_recharging()# bool
core.data.ship.fuel_pct()          # float | None — fuel percentage
core.data.ship.fuel_tons()         # float | None — FuelMain in tons
core.data.ship.fuel_rate()         # float | None — burn rate t/hr
core.data.ship.fuel_remaining_s()  # float | None — seconds of fuel left
core.data.ship.identity()          # dict — {name, ident, type, type_display, rebuy, value}

# Commander
core.data.commander.name()         # str | None
core.data.commander.location()     # dict — {system, body}
core.data.commander.credits()      # float | None — CAPI > journal
core.data.commander.ranks()        # dict — all rank types
core.data.commander.powerplay()    # dict — {power, rank, merits_total}
core.data.commander.squadron()     # dict — {name, tag, rank}
core.data.commander.mode()         # str | None — "Solo", "Group", etc.

# Fleet — CAPI primary, journal fallback
core.data.fleet.current_ship()     # dict | None
core.data.fleet.stored_ships()     # list[dict]
core.data.fleet.stored_modules()   # list[dict]
core.data.fleet.carrier()          # dict | None

# Market — CAPI docked+authed, Market.json otherwise
core.data.market.commodities()     # dict {name_lower: commodity_dict}
core.data.market.station_info()    # dict {station_name, market_id, star_system}
core.data.market.mean_prices()     # dict {name_lower: int}

# Fighter / NPC crew
core.data.crew.active()            # bool
core.data.crew.name()              # str | None
core.data.crew.rank()              # str | None
core.data.crew.slf_hull()          # int pct
core.data.crew.slf_deployed()      # bool
core.data.crew.has_fighter_bay()   # bool
```

### `core.data.events()` — event ring buffer

Request recent journal events of any type without scanning the journal yourself:

```python
# Last 5 HullDamage events, newest first
recent = core.data.events("HullDamage", n=5)
for ev in recent:
    print(ev["Health"], ev["_logtime"])

# Most recent FSDJump
last_jump = core.data.events("FSDJump", n=1)
if last_jump:
    system = last_jump[0].get("StarSystem")
```

The buffer holds the last 200 events per type across the full session.

### `core.data.source()` — transparency

```python
# Find out which source provided a data value
src = core.data.source("ship.hull")
# Returns: "capi" | "journal" | "status_json" | "unknown"
```

### `core.data.capi` — CAPI auth state

```python
core.data.capi.is_connected()        # bool
core.data.capi.commander_name()      # str | None
core.data.capi.last_poll("profile")  # float (unix timestamp)
```

### Other `core` APIs

```python
core.emitter.emit(              # send terminal / Discord message
    msg_term="Kill: Cobra",
    msg_discord="**Kill: Cobra**",
    emoji="💥", sigil="*  KILL",
    timestamp=logtime,
    loglevel=core.notify_levels["RewardEvent"],
)

core.plugin_call("session_stats", "on_new_session", gap)  # call another plugin
core.active_session   # SessionData — current session counters
core.app_settings     # dict — user settings from config.toml
core.notify_levels    # dict — per-event notification levels
core.gui_queue        # thread-safe queue for GUI messages (None in headless mode)
core.cfg              # ConfigManager
```

---

## Receiving events

List journal event names in `SUBSCRIBED_EVENTS`. Your `on_event()` method
receives the parsed event dict with `_logtime` already set:

```python
SUBSCRIBED_EVENTS = ["Bounty", "FactionKillBond", "Died"]

def on_event(self, event: dict, state) -> None:
    ev      = event.get("event")
    logtime = event.get("_logtime")   # datetime object, or None during preload

    match ev:
        case "Bounty":
            value = event.get("TotalReward") or event["Rewards"][0]["Reward"]
            ship  = event.get("Target_Localised") or event.get("Target")
            # ...
        case "Died":
            rebuy = event.get("Cost", 0)
            # ...
```

> **Important:** do not raise exceptions in `on_event()`. Uncaught exceptions
> are caught and logged as warnings, but they abort processing for that event.

### Preload awareness

`state.in_preload` is `True` while EDMD is replaying historical journal events.
Avoid emitting alerts or writing to the GUI queue during preload:

```python
def on_event(self, event: dict, state) -> None:
    if state.in_preload:
        return   # skip — historical event
    # ... live event handling
```

---

## Registering a GUI block

If your plugin needs a dashboard panel, call `core.register_block(self)` in
`on_load()` and implement the `BlockWidget` interface in your GUI module.

```python
def on_load(self, core) -> None:
    super().on_load(core)
    core.register_block(self, priority=50)   # lower priority = displayed first

# Default grid position (can be overridden by user)
DEFAULT_COL    = 16
DEFAULT_ROW    = 0
DEFAULT_WIDTH  = 8
DEFAULT_HEIGHT = 10
```

See `gui/block_base.py` for the `BlockWidget` base class. Your block class
lives in `gui/blocks/myplugin.py` and is registered in `gui/blocks/__init__.py`.

---

## Persistent storage

Each plugin gets a sandboxed storage directory:

```python
# In on_load():
self.storage.write_json({"key": "value"}, "data.json")

# In on_event():
saved = self.storage.read_json("data.json")
```

Allowed filenames: `data.json`, `config.json`, `state.json`, `tokens.json`.

---

## Plugin tiers

EDMD loads plugins in three tiers. Understanding this helps explain what you
see in Settings → Plugins:

| Tier | Location | Always on | Shown in menu |
|------|----------|-----------|---------------|
| Core components | `core/components/` | ✅ | ❌ |
| Activity plugins | `builtins/activity_*/` | ✅ | ❌ |
| Data integrations | `builtins/eddn|edsm|edastro|inara/` | ❌ | ✅ |
| Third-party | `plugins/*/` | ❌ | ✅ |

**Core components** (alerts, commander, cargo, crew, engineering, assets,
missions, session stats) are always enabled. Users can hide their dashboard
blocks via View → Blocks but cannot disable the underlying plugin.

**Your plugins** live in `plugins/` — tier 4. They can be enabled and disabled
by the user via Settings → Plugins.

---

## Data priority

When `core.data` returns a value, it follows this priority order:

1. **CAPI** — Frontier Companion API (requires user authentication)
2. **Journal events** — live from the `.log` file tailed by EDMD
3. **Local JSON** — `Status.json`, `Market.json`, `Shipyard.json`

If CAPI is not authenticated, journal and JSON data are used throughout.
If CAPI is authenticated but a poll hasn't completed yet, journal data fills in.

You do not need to handle this yourself — `core.data` resolves it transparently.

---

## Activity provider plugins

If your plugin tracks session activity and wants a tab in the Session Stats
block, implement `ActivityProviderMixin`:

```python
from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin

class MyActivityPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME        = "my_activity"
    ACTIVITY_TAB_TITLE = "My Activity"
    SUBSCRIBED_EVENTS  = ["SomeEvent"]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self.count = 0

    def on_session_reset(self) -> None:
        self.count = 0

    def has_activity(self) -> bool:
        return self.count > 0

    def get_summary_rows(self) -> list[dict]:
        return [{"label": "Things done", "value": str(self.count), "rate": None}]

    def get_tab_rows(self) -> list[dict]:
        return self.get_summary_rows()

    def on_event(self, event: dict, state) -> None:
        if event.get("event") == "SomeEvent":
            self.count += 1
```

Tabs appear automatically in Session Stats when `has_activity()` returns `True`,
sorted alphabetically after the Summary tab.

---

## Example: minimal kill counter plugin

```python
from core.plugin_loader import BasePlugin

class KillCounterPlugin(BasePlugin):
    PLUGIN_NAME        = "kill_counter"
    PLUGIN_DISPLAY     = "Kill Counter"
    PLUGIN_VERSION     = "1.0.0"
    PLUGIN_DESCRIPTION = "Counts kills and announces milestones."
    SUBSCRIBED_EVENTS  = ["Bounty", "FactionKillBond"]

    def on_load(self, core) -> None:
        super().on_load(core)
        self.kills = 0

    def on_event(self, event: dict, state) -> None:
        if state.in_preload:
            return
        self.kills += 1
        if self.kills % 100 == 0:
            core = self.core
            core.emitter.emit(
                msg_term=f"Milestone: {self.kills} kills this session!",
                emoji="🎯", sigil="*  MILE",
                timestamp=event.get("_logtime"),
                loglevel=core.notify_levels.get("RewardEvent", 1),
            )
```

---

## Further reading

- `core/data.py` — full `DataProvider` source with inline docs
- `core/activity.py` — `ActivityProviderMixin` protocol
- `core/plugin_loader.py` — `BasePlugin`, `PluginStorage`
- `gui/block_base.py` — `BlockWidget` base class
- `builtins/activity_combat/plugin.py` — example activity provider
- `builtins/eddn/plugin.py` — example integration plugin
