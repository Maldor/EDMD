# EDMD Release Notes

---

## 20260402

**Elite Dangerous Monitor Daemon — EDMD**

Major feature release. Introduces per-commander data isolation, a new Career
block with lifetime statistics sourced from the game's authoritative Statistics
event, a dedicated Mission Stack block with full per-faction analysis and
cross-restart persistence, and a rewritten At-Risk Holdings tracker. Includes
a new grid layout engine with 32-column resolution and 10 px row snapping, new
Exploration, Exobiology, and PowerPlay career reports, and a comprehensive run
of bug fixes across the ship roster, mission tracking, integration plugin queue
handling, and Windows launcher behaviour.

---

### Feature — Per-Commander Data Isolation

All persistent data is now namespaced by Frontier account ID (FID). Plugin
storage, layout, catalog, session state, and integration queues are written
under `~/.local/share/EDMD/commanders/<FID>/` rather than directly into the
EDMD data root. Multi-pilot setups on a shared machine or a shared filesystem
are now cleanly isolated by default.

On first launch after upgrading, EDMD scans the most recent journals for the
account FID, then moves any files found at their legacy flat locations into the
per-commander path. The migration is a one-time, no-op-if-already-done
operation — no data is lost and no user action is required.

New state functions: `cmdr_data_dir()`, `set_active_fid()`, `get_last_fid()`,
`migrate_legacy_cmdr_files()`.

Config key `pilot_fid` is now populated from the `Commander` or `LoadGame`
journal event as early as possible so that all plugin storage paths resolve
correctly before any events are processed.

---

### Feature — Career Block

A new **Career** dashboard block displays lifetime statistics sourced from the
game's `Statistics` journal event — Frontier's authoritative server-side career
totals — supplemented by journal-derived figures where the Statistics event
offers no coverage.

The block mirrors the Session Stats layout: a Summary tab with top-level
figures and per-domain activity tabs for Combat, Exploration, Exobiology,
Mining, Trade, and PowerPlay.

Data is produced by a new `JournalHistoryPlugin` that scans all journal files
once at startup in a daemon thread and exposes aggregated career data via a
`threading.Event`. The Career block shows "Scanning…" until the scan completes,
then refreshes automatically.

PowerPlay data includes current merit total and a per-system breakdown of
merits earned, sourced from `PowerplayMerits` journal events. The merit total
displayed is always the authoritative `TotalMerits` field from the most recent
`PowerplayMerits` event rather than a running sum of `MeritsGained`, which
diverges due to server-side wing kill award adjustments.

---

### Feature — Mission Stack Block

A new **Mission Stack** dashboard block replaces the mission analysis that
previously lived inside the Session Stats Missions tab.

The block shows a full per-source-faction breakdown of the active massacre
stack: kill count required per mission, live kills-this-session progress (via
`Bounty.VictimFaction` attribution), total reward, and a delta-to-stack-height
indicator showing how many kills each faction is above or below the maximum.
Mixed-target and mixed-type warnings are displayed when the stack spans more
than one target faction or ship type. Redirected-mission progress is tracked
and shown in a completion row.

Mission detail — kill counts, factions, rewards, target ship types — is
persisted to plugin storage on every change and restored on startup, so the
block is fully populated immediately on launch without waiting for journal
events.

On startup, two recovery paths ensure complete data even when missions were
accepted across multiple journal sessions:

- **Backfill scan.** After the `Missions` bulk event builds skeleton entries
  (which carry no kill counts), EDMD scans journals backwards for matching
  `MissionAccepted` events and enriches each skeleton with its original detail.

- **Preload accept.** `MissionAccepted` events in the current journal that
  appear after the `Missions` bulk snapshot are now processed during preload
  when the mission ID is not yet tracked, rather than being silently dropped
  by an overly broad preload guard.

The `Missions` bulk-event handler now also fires when `mission_detail_map` is
empty, closing a gap where `bootstrap_missions()` — which runs unconditionally
at startup — sets `state.missions = True` but does not populate the detail map,
causing the handler's previous `not state.missions` guard to skip backfill
entirely.

---

### Feature — Career Reports: Exploration, Exobiology, PowerPlay

Three new career reports are available from the Reports Viewer:

**Exploration** — lifetime scan totals (systems, bodies, FSS, DSS, first
discoveries), cartography sold by system, and terraformable planet counts, all
sourced from the `Statistics` event for Frontier-authoritative totals.

**Exobiology** — career samples by genus, total sold value, and top species by
value, sourced from the `Statistics` event and supplemented by journal
`SellOrganicData` history.

**PowerPlay** — current merits, power allegiance, rank, total merits earned,
and a per-system merit breakdown sourced from `PowerplayMerits` events across
all journals.

All three reports use `_get_latest_statistics()` to pull the most recent
`Statistics` event from the journal directory, guaranteeing that career totals
reflect Frontier's server state rather than a running tally that can diverge.

---

### Feature — Holdings Tracker Rewrite

`HoldingsPlugin` is rewritten from scratch as v2.0.

**Bootstrap on every startup.** The tracker now rebuilds its full at-risk
balance from all journal files on every startup via a daemon thread
(`_bootstrap_all`). This eliminates the class of drift bugs where cached state
diverged from actual journal history across restarts, and removes the
dependency on a prior `holdings.json` snapshot being correct.

**Composite voucher deduplication.** Vouchers are now keyed by
`(timestamp, event, amount)` rather than timestamp alone. Two `Bounty` events
that fire at the same second — common in multi-faction combat zone kills — have
different reward amounts and must both count. The old single-timestamp key
silently dropped the second event.

**Broker percentage corrected.** `RedeemVoucher.Amount` is what the player
received after the broker cut is taken. The tracker now subtracts `Amount`
directly when a voucher is redeemed rather than computing an inflated face
value from `BrokerPercentage`. Using the face value overstated what was cleared
from the ledger.

---

### Enhancement — Grid Layout: 32-Column Engine

The dashboard grid is upgraded from 24 columns to 32, halving the column unit
width (~53 px → ~40 px at 1280 px canvas) and providing 33% more horizontal
snap points for block placement and resizing.

Row height is reduced from 20 px to 10 px per unit, doubling vertical snap
precision. All `DEFAULT_LAYOUT` heights are scaled accordingly so the visual
dashboard arrangement is preserved.

Gap between blocks is reduced from 4 px to 2 px.

The minimum block width is reduced from 4 to 3 column units. Layout files now
carry a `"version"` key; files written by the old 24-column engine are
automatically discarded and replaced with the new defaults on first launch.

New constants: `COLS = 32`, `ROW_PX = 10`, `GAP = 2`, `MIN_W = 3`,
`LAYOUT_VERSION = 2`.

---

### Fix — Assets Block: Ship Roster Ghost Ships and Missing Ships

Three compounding roster bugs are resolved.

**Ghost ships from additive CAPI merge.** Previous code merged CAPI ship data
additively into the stored fleet on every poll, so ships that had been sold
between polls accumulated as ghost entries. CAPI is now treated as the
authoritative, non-additive fleet source: the stored list is replaced entirely
on each CAPI update.

**Ships absent after swap before re-poll.** When CAPI was last polled while
ship A was the current ship, ship A lived in `profile["ship"]` rather than
`profile["ships"]`. If the player then swapped to ship B before the next poll,
ship A moved to stored — but CAPI still showed it as current and `ships{}`
didn't include it. On restart, the roster code built `capi_owned_ids` only
from `ships{}`, so ship A was excluded from every subsequent lookup.

Resolved by: (1) always including `profile["ship"]["id"]` in `capi_owned_ids`;
(2) supplementing `capi_owned_ids` with ship IDs seen in recent `StoredShips`
journal events; (3) building journal-sourced roster entries for ships in
`capi_owned_ids` that have no corresponding entry in `capi_ships_raw`.

**Raw internal name displayed as ship type.** When CAPI returned a ship's
`nameLocalized` field as an unprocessed internal string (e.g. `"Type9_Military"`
or `"Smallnx01"`), the Assets Ships tab displayed the raw string rather than
the localised name. The roster commit now applies a sanitise pass to
`assets_current_ship` — in addition to the existing pass on stored ships — that
detects any `type_display` without spaces and forces it through the localisation
pipeline. The live `Loadout` event handler applies the same check.

The static ship name map gains entries for Kestrel Mk II variants reported by
CAPI under several internal name formats (`"smallnx01"`, `"small_nx01"`,
`"smallcombat01nx"`).

---

### Fix — Assets Block: Current Ship Type Display

When `_load_capi_profile_from_disk` set `assets_current_ship.type_display`
from a stale `capi_profile.json` containing a raw internal ship name, the value
persisted into the Assets Ships tab because the existing sanitise pass only
iterated `assets_stored_ships`. The sanitise pass is now also applied to
`assets_current_ship` at the end of `_scan_and_refresh`, after the journal
`Loadout` scan has had opportunity to correct it.

---

### Fix — Fuel Status: Display Simplified

The fuel status line in the vessel summary previously showed both the burn rate
(`3.32 t/hr`) and the estimated time remaining. The burn rate figure is
computed over a small window of `ReservoirReplenished` events and can be noisy
early in a flight. The line now shows time remaining only (`~21h 4m`), which is
the figure commanders actually act on.

---

### Fix — Inara Integration: Queue File Not Cleared After Send

After successfully sending a batch to the Inara API, the sender thread called
`_queue_file().unlink()` — the module-level function — rather than
`self._queue_file.unlink()`. The module-level function returns
`cmdr_data_dir() / "inara_queue.jsonl"` while the sender writes to
`self.storage.path / "queue.jsonl"`. These are different paths. The unlink
silently missed its target on every send cycle, leaving the queue file on disk
permanently and causing the full queue to be re-sent on the next startup.

---

### Fix — Windows Launcher: Missing GCC Runtime DLL

`EDMD.exe` failed immediately on machines without a MinGW installation in
`PATH` with `"libgcc_s_seh-1.dll was not found"`. The PyInstaller spec now
searches common MSYS2 install locations for `libgcc_s_seh-1.dll` at build time
and bundles it alongside the executable when found. An `MSYS2_ROOT` environment
variable override is supported for non-standard MSYS2 install paths.

---

### Files Changed

| File | Change |
|------|--------|
| `core/state.py` | `cmdr_data_dir()`, `set_active_fid()`, `get_last_fid()`, `migrate_legacy_cmdr_files()` added; `pilot_fid` field; Kestrel Mk II variants in ship name map; VERSION → 20260402 |
| `core/plugin_loader.py` | `cmdr_data_dir()` for all storage paths; `write_sibling_json()` added; `_states_file()` updated |
| `core/emit.py` | Fuel status line shows time remaining only |
| `core/reports.py` | `report_exploration()`, `report_exobiology()`, `report_powerplay()` added; `_get_latest_statistics()` helper |
| `core/journal.py` | `bootstrap_missions()` guard fixed; session clock anchor moved to plugin dispatch path |
| `core/components/holdings/plugin.py` | Full rewrite v2.0: daemon-thread bootstrap, composite voucher key, broker amount fix |
| `core/components/missions/plugin.py` | `_persist()`, `_restore()` added; backfill scan; preload `MissionAccepted` guard fixed; Missions case guard fixed to fire when `mission_detail_map` is empty |
| `core/components/assets/plugin.py` | `capi_owned_ids` supplemented from CAPI current ship and `StoredShips` journal events; `journal_only_ids` build path; `assets_current_ship` sanitise pass; live `Loadout` handler sanitise; CAPI treated as non-additive roster source |
| `core/components/journal_history/plugin.py` | New — background full-journal scanner; `Statistics` event capture |
| `core/components/commander/plugin.py` | FID population from `Commander`/`LoadGame` events |
| `core/components/catalog/plugin.py` | Lazy DB path via `cmdr_data_dir()` |
| `gui/grid.py` | 32-column engine; `ROW_PX = 10`; `GAP = 2`; `MIN_W = 3`; `LAYOUT_VERSION = 2`; version-checked `_load()` |
| `gui/app.py` | `CareerBlock` registered; `career_update` message routed |
| `gui/blocks/career.py` | New — lifetime statistics block |
| `gui/blocks/missions.py` | New — Mission Stack block with per-faction breakdown |
| `gui/blocks/session_stats.py` | Career tab removed; mission stack analysis removed from Missions tab |
| `gui/blocks/__init__.py` | `CareerBlock` exported |
| `builtins/activity_missions/plugin.py` | Stack analysis removed from `get_summary_rows()` and `get_tab_rows()` |
| `builtins/inara/plugin.py` | Queue file unlink uses `self._queue_file` |
| `edmd.py` | FID scan; migration call; `cmdr_data_dir()` for `_dp_storage` |
| `edmd_launcher.spec` | `libgcc_s_seh-1.dll` bundled from MSYS2 search paths |
