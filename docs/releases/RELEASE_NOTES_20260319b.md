# EDMD Release Notes — 20260319b

**Elite Dangerous Monitor Daemon**

Major architecture release. Introduces a unified `DataProvider` as the single
source of truth for all game state, absorbs CAPI into core, promotes all
non-integration builtins to always-on core components, and introduces a
three-tier plugin loading model.

---

## Architecture — Unified DataProvider (`core/data.py`)

All game state previously scattered across individual plugin `state.*` writes
is now accessible through a single typed API: `core.data`.

```python
core.data.ship.hull()           # int pct — CAPI > Loadout event
core.data.ship.fuel_pct()       # float — Status.json > ReservoirReplenished
core.data.ship.fuel_rate()      # float t/hr — commander rolling estimate
core.data.commander.credits()   # float — CAPI > journal
core.data.fleet.current_ship()  # dict — CAPI profile > journal Loadout
core.data.market.commodities()  # dict — CAPI market > Market.json
core.data.events("HullDamage", n=5)  # last N events from ring buffer
core.data.source("ship.hull")   # "capi" | "journal" | "status_json"
```

Data priority is `CAPI > journal events > local JSON`. If CAPI is not
authenticated the journal and JSON sources fill in transparently.
Consumers never handle source selection themselves.

---

## Architecture — CAPI absorbed into DataProvider

`builtins/capi/` is removed. All OAuth flow, token management, background
polling, and data extraction that previously lived there now lives in
`core/data.py` as `CAPISource`, an internal component of `DataProvider`.

CAPI authentication is still user-configurable via Settings → Preferences.
The UI now talks directly to `core.data.capi` instead of the capi plugin.

**Delete from repo:** `builtins/capi/`

---

## Architecture — Event Ring Buffer

Every journal event is pushed into a per-type ring buffer (last 200 events
per type) accessible via `core.data.events(type, n)`. Plugins and components
no longer need to scan journal files or maintain their own event history.

---

## Architecture — Core Components

Nine builtins promoted to always-on core components in `core/components/`:

- `alerts` — combat and ship alerts
- `assets` — fleet, wallet, modules, carrier
- `cargo` — hold inventory, Spansh price comparison
- `commander` — pilot identity, location, fuel, hull, shields
- `crew_slf` — NPC crew and fighter bay
- `engineering` — materials inventory
- `missions` — massacre mission stack
- `session_stats` — session clock and tabbed activity summary
- `spansh` — market price fetcher

These are always enabled. Users control visibility via View → Blocks.
They do not appear in Settings → Plugins.

**Delete from repo:**
```
builtins/alerts/
builtins/assets/
builtins/cargo/
builtins/commander/
builtins/crew_slf/
builtins/engineering/
builtins/missions/
builtins/session_stats/
builtins/spansh/
builtins/capi/
```

---

## Architecture — Three-Tier Plugin Loader

`core/plugin_loader.py` now loads in three tiers:

| Tier | Location | Always on | In menu |
|------|----------|-----------|---------|
| Core components | `core/components/` | ✅ | ❌ |
| Activity + integrations | `builtins/` | activity: ✅, integrations: ❌ | integrations only |
| Third-party | `plugins/` | ❌ | ✅ |

Settings → Plugins now shows only data integrations (EDDN, EDSM, EDAstro,
Inara) and user-installed third-party plugins. Core components and activity
plugins are hidden from the menu.

---

## Plugin Development Guide updated

`docs/PLUGIN_DEVELOPMENT.md` fully rewritten for the new architecture:

- `core.data` API reference with all sub-namespaces documented
- Event ring buffer usage (`core.data.events()`)
- Source transparency (`core.data.source()`)
- Three-tier plugin model explained
- Activity provider example updated
- Data priority order documented

---

## Preferences — CAPI auth

CAPI connect/disconnect in Settings → Preferences now talks to
`core.data.capi` directly. The auth flow, token storage, and status display
work identically to before — the change is internal.

---

## Upgrading from 20260319

**After extracting this archive, delete these directories from your repo:**
```
builtins/alerts/
builtins/assets/
builtins/cargo/
builtins/commander/
builtins/crew_slf/
builtins/engineering/
builtins/missions/
builtins/session_stats/
builtins/spansh/
builtins/capi/
```

No `config.toml` changes required. Delete `~/.local/share/EDMD/layout.json`
only if the default grid layout has changed (it has not in this release).

---

## Known limitations / next steps

- Core components still inherit `BasePlugin` and go through the plugin loader.
  A future release will give them a lighter `CoreComponent` base class and
  wire them directly rather than through plugin dispatch.
- `core.data` sub-namespaces are read-only views over `MonitorState` fields.
  Future: components write directly to `DataProvider` stores rather than
  to raw `state.*` fields.
