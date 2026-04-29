# EDMD Release Notes

---

## 20260317

**Elite Dangerous Monitor Daemon — EDMD**

Focused release. Completes the Cargo block with live target-market price
comparison via Spansh, overhauled Crew / SLF block header with correct fighter
identification throughout, and a complete rewrite of all SLF type name mappings
based on authoritative game data.

---

### Feature — Cargo Block: Target Market Price Comparison (Spansh)

The Cargo block footer now contains a station search field. Type any station
name (minimum 3 characters) to query Spansh.co.uk for matching stations. A
popover shows up to 5 results with system name and data age. Selecting a result
immediately loads that station's commodity sell prices as the comparison column.

**Column layout when a target is set:**

| Col | Header | Prices |
|-----|--------|--------|
| 2 | `Rominger City \| HIP 94521` | Target sell prices (Spansh) |
| 3 | `Gal. Avg` | Galactic average (from last docked Market.json) |

When no target is set, col 2 shows the last docked station's sell prices and
col 3 shows galactic average — unchanged from the previous release.

**Target persistence:** the selected station is saved to
`~/.local/share/EDMD/plugins/spansh/data.json` and re-fetched automatically
on the next EDMD startup. Prices refresh every 30 minutes in the background.
The refresh interval is appropriate for Spansh's crowd-sourced EDDN data which
is typically 0–4 hours old for active stations.

**Spansh API note:** Spansh does not expose galactic average prices. The `Gal.
Avg` column always comes from `Market.json` (written when you dock and open the
commodities screen, or when you select a comparison station on the galaxy map).

**Input format:** station name only — `Rominger City`. If multiple stations
share a name, append the system: `Rominger City, HIP 94521`.

---

### New Builtin — `spansh` Plugin

`builtins/spansh/plugin.py` — Spansh market price fetcher. Provides
`search(query)` and `set_target(name, system, _record)` as a plugin API for
the Cargo block. Network requests run on background threads; the GUI never
blocks. If the Spansh plugin is disabled or absent, the Cargo block degrades
gracefully — the search UI is simply not shown.

State fields written:

| Field | Type | Contents |
|-------|------|----------|
| `cargo_target_market` | `dict` | Market info dict (same schema as `cargo_market_info`) |
| `cargo_target_market_name` | `str` | `"Station \| System"` display string |
| `cargo_target_market_ts` | `float` | Epoch time of last successful fetch |

---

### Feature — Cargo Block: Market Refresh on Dock

The Cargo block now subscribes to `Docked` and `Location` journal events in
addition to `Market`. `Market.json` is re-read immediately on docking, so the
sell column header and prices update as soon as the player lands — without
needing to open the commodities screen.

---

### Feature — Crew / SLF Block: Correct Fighter Identification

All SLF type names have been corrected based on authoritative game data:

| Journal type key | Fighter | Faction | Manufacturer |
|-----------------|---------|---------|--------------|
| `empire_fighter` | **GU-97** | Imperial | Gutamaya |
| `federation_fighter` | **F63 Condor** | Federal | Core Dynamics |
| `independent_fighter` | **Taipan** | Independent / Alliance | Faulcon DeLacy |

The previous mapping was incorrect: `independent_fighter` was mapped to
"F63 Condor" and `federation_fighter` to "F/A-26 Strike" (a non-existent ship).

**Variant identification** now uses both the fighter type and the bay slot
key. The five standard loadout slots per fighter type:

| Journal `Loadout` key | GU-97 | F63 Condor | Taipan |
|----------------------|-------|------------|--------|
| `one` | Gelid F | Gelid F | Gelid F |
| `two` | Rogue F | Rogue F | Rogue F |
| `three` | Aegis F | Aegis F | Aegis F |
| `four` | **Gelid G** | **Gelid G** | **Gelid G** |
| `five` | **Rogue G** | **Rogue G** | **Rogue G** |

`F` = Fixed weapons; `G` = Gimballed weapons. Grade suffixes `_g1`/`_g2`/`_g3`
denote engineering tiers. The Taipan uniquely has an `at` slot = `AX1 F`
(anti-xeno fixed multi-cannon). Guardian SLFs corrected to `XG7 Trident`,
`XG8 Javelin`, `XG9 Lance`.

**`slf_known_ft` state field:** `RestockVehicle` events now store the fighter
type (`empire_fighter`, etc.) separately from the resolved display name. When
`LaunchFighter` fires without a `Type` field (a Frontier limitation when only
one type is stocked), EDMD uses `slf_known_ft` + the `Loadout` key to resolve
the exact variant — `empire_fighter` + `four` → `GU-97 (Gelid G)`.

---

### Feature — Crew / SLF Block: Overhauled Header

The block header now matches the Commander block's two-line layout:

```
CREW: Valerie Holcomb                          GU-97
Combat Rank: Elite                            Gelid G
```

- **Line 1:** crew name (left, full header style) | fighter base type (right)
- **Line 2:** combat rank (left, full header style) | fighter variant (right)
- Line 2 is visible when either rank or variant is present

Rank label previously used `data-key` (muted grey); it now inherits
`section-header` styling for visual parity with the Commander block.

---

### Fix — SLF Bootstrap: Ship Identity Filtering

The bootstrap journal scan that recovers SLF type on startup (`_bootstrap_type_from_journals`)
previously failed silently due to a wrong attribute name (`core.cfg.journal_folder`
instead of `core.journal_dir`). This caused EDMD to fall back to stale `data.json`
values from previous ships. Fixed: the scan now correctly identifies all your
journal files, walks backwards newest-first, and only accepts `RestockVehicle`
events that occurred while the current ship (`ShipID`) was active.

---

### Fix — SLF Bootstrap: stale type from other ships

When swapping ships, the previous `slf_type` from another ship's fighter was
persisting because the bootstrap's fallback (when `current_sid` was `None`)
accepted the first `RestockVehicle` found regardless of ship. The fix:

1. `Loadout` events now immediately store `state.slf_ship_id` — available
   before the assets plugin has populated `assets_current_ship`.
2. Bootstrap uses `slf_ship_id` exclusively; returns immediately if unknown
   rather than guessing.
3. `ShipyardSwap` clears `slf_type`, `slf_deployed`, and `slf_docked` so stale
   fighter data from the previous ship never bleeds into the new ship's display.

---

### Fix — Cargo Block: Double Search Suppressed

Programmatic `entry.set_text()` calls in `refresh()` were triggering the GTK
`changed` signal, launching a second Spansh search. Suppressed with an
`_updating_entry` boolean flag that guards the `_on_search_changed` handler.

---

### Default Grid Layout Updated

| Block | Col | Row | W | H | Change |
|-------|-----|-----|---|---|--------|
| commander | 0 | 0 | 8 | 14 | — |
| session_stats | 8 | 0 | 8 | 10 | — |
| crew_slf | 16 | 0 | 8 | **12** | **+2** — expanded header |
| missions | 0 | 14 | 8 | 9 | — |
| mode | 8 | 10 | 8 | 5 | — *(hidden)* |
| cargo | 8 | 15 | 8 | 10 | — |
| engineering | 8 | 25 | 8 | 10 | — |
| alerts | 0 | 23 | 8 | 10 | — |
| assets | 16 | **12** | 8 | 25 | **row +2** — follows crew_slf |

---

### Theme — New CSS Classes

Added to `themes/base.css`:

| Class | Purpose |
|-------|---------|
| `.cargo-full` | Capacity gauge at 100% — red |
| `.cargo-warn` | Capacity gauge ≥ 75% — amber |
| `.cargo-ok` | Capacity gauge < 75% — green |
| `.cargo-stolen` | Stolen cargo item name — amber |
| `.data-entry` | Footer search entry field |
| `.cargo-accept-btn` | Green ✓ accept button |
| `.cargo-clear-btn` | Red ✕ clear button |

Custom themes that override `base.css` may wish to add these classes.

---

### Upgrading

Delete `~/.local/share/EDMD/layout.json` to apply the updated grid (crew_slf
expanded by 2 rows, assets shifted down by 2). Existing layouts will continue
to work; only the crew_slf block may appear slightly short until manually
resized.

No `config.toml` changes required.

---

### Known Limitations

- Spansh does not expose galactic average prices — the `Gal. Avg` column is
  always sourced from `Market.json` (docked station data).
- Spansh crowd-sourced market data may be hours old for less-travelled stations.
- SLF type variant will be unknown until a `RestockVehicle` event exists in
  the journal history for the current ship. Docking and using the fighter bay
  creates this event.
- GTK4 GUI is Linux-native; Windows and macOS are best-effort.
- Block collapse state is not persisted across restarts.


---

## 20260316

**Elite Dangerous Monitor Daemon — EDMD**

Major release. Implements full CAPI integration as the primary data source for
the Assets block, adds squadron identity to the Commander block, overhauls the
Cargo block layout, fixes ship/module name normalisation throughout, and adds
cross-plugin data sharing infrastructure.

---

### Feature — CAPI as Primary Data Source

CAPI poll results are now persisted to disk immediately after each endpoint
response. Every other plugin that needs CAPI data reads these cached files on
startup rather than waiting for a re-poll.

**Files written to `~/.local/share/EDMD/plugins/capi/`:**

| File | Contents |
|------|----------|
| `capi_profile.json` | Full `/profile` response — commander, current ship with loadout, stored ships, suits, squadron |
| `capi_market.json` | Last docked `/market` response — commodity prices, supply, demand |
| `capi_shipyard.json` | Last docked `/shipyard` response — available ships and modules |
| `capi_fleetcarrier.json` | `/fleetcarrier` response — carrier state, services, cargo, finances |
| `capi_communitygoals.json` | `/communitygoals` response — active CGs and commander contributions |

These files are refreshed on every poll cycle. Any plugin can read sibling
plugin files via `self.storage.read_sibling_json(plugin_name, filename)` — a
new method on `PluginStorage` that allows cross-plugin data access (read-only).

**New `/communitygoals` endpoint** is now polled on every dock cycle with a
5-minute cooldown. Results are stored in `state.capi_community_goals` for use
by future CG blocks.

---

### Feature — Assets Block: CAPI-Sourced Fleet with Full Loadouts

The Assets block Ships tab is now sourced from CAPI on startup:

- **Fleet roster** is authoritative — Frontier's server provides exactly the
  ships you currently own. Sold ships are never displayed.
- **Stored ship loadouts** are sourced from journal `Loadout` events accumulated
  across sessions, validated against the CAPI roster so only owned ships are
  included. Loadouts persist in `data.json` between sessions.
- **Hull percentage and rebuy cost** come from CAPI for all ships.
- **Ship type names** are normalised through `normalise_ship_name()` — all
  internal names (`SmallCombat01_NX`, `LakonMiner`, `Type9_Military`) resolve
  to correct in-game display names (`Kestrel Mk II`, `Type-11 Prospector`,
  `Type-10 Defender`).

On startup, `_load_capi_profile_from_disk()` runs synchronously in `on_load`
before the background journal scan, giving immediate complete fleet data with
no delay.

> **CAPI tradeoff:** when CAPI is disabled, the fleet roster falls back to the
> most recent `StoredShips` journal event. Ships sold between sessions may
> appear until the next dock. Hull % and rebuy costs are unavailable for stored
> ships. Loadout data is unaffected. See `CONFIGURATION.md` for details.

---

### Feature — Assets Block: Module Name Normalisation

Module display names now use correct in-game format throughout:

- **Core / Optional internals** show size+class prefix: `8A Shield Generator`,
  `5D Life Support`, `7A Universal Multi-Limpet Controller`
- **Hardpoints and utility mounts** show no size prefix (size is conveyed by
  slot): `Plasma Shock Cannon Mk.II (Fixed)`, `Remote Release Flak Launcher
  (Turret)`, `Kill Warrant Scanner`
- **Armour** resolves by grade: `Lightweight Alloy`, `Military Grade
  Composite`, `Reactive Surface Composite`
- **Engineering** blueprints and experimental effects use localised names:
  `Dirty Drive Tuning`, `Long Range`, `Oversized`, `Deep Plating`
- **Livery, cosmetics, cockpit, and cargo hatch** are filtered from module
  display — only fitted hardware is shown
- `PlanetaryApproachSuite` correctly categorised as Optional Internal

Hardpoint and livery name coverage is ongoing — remaining unrecognised modules
fall through to a cleaned title-case fallback.

---

### Feature — Assets Block: Stored Modules Engineering Fixed

`_parse_stored_modules` now reads the correct journal field names:

- `BuyPrice` (not `Value`) for module value — was always showing `0 cr`
- `EngineerModifications` (flat string, not nested `Engineering` dict) for
  blueprint name — engineering was silently absent for all stored modules

---

### Feature — Commander Block: Squadron Identity

When the commander is a member of a squadron, the block header now shows:

```
CMDR NAME  —  Squadron Rank
SQUADRON NAME  [TAG]
SHIP NAME | IDENT
```

Squadron data is sourced from the CAPI `/profile` `squadron` object on every
poll and at startup from the cached `capi_profile.json`.

---

### Feature — Cargo Block: Aligned Grid Layout

The Cargo block is now built on a single `Gtk.Grid` spanning all rows — header,
column labels, category headers, item rows, and totals. This is the only
reliable way to guarantee pixel-perfect column alignment in GTK4 when mixing
static header rows with a scrollable content area.

Column layout:
- **Col 0** — Item name (hexpand)
- **Col 1** — Qty (fixed width, `N t` format)
- **Col 2** — Sell price at last docked station
- **Col 3** — Galactic average price

The market reference row (`StationName | StarSystem` centred over the Sell
column, `Gal. Avg` over the Avg column) is always the top row. The column
label row (`Item | Qty. | Sell | —`) sits below it. Items are grouped by
`Category_Localised` then sorted by name. Totals row has visual breathing room
above it.

---

### Infrastructure — `PluginStorage.read_sibling_json()`

New method on `PluginStorage` allows any plugin to read files written by
another plugin (read-only cross-plugin data access):

```python
data = self.storage.read_sibling_json("capi", "capi_profile.json")
```

The method validates filenames against the same allowlist as `write_json`,
prevents path traversal, and returns an empty dict if the file is absent or
unparseable.

Allowed filenames are expanded to include `capi_profile.json`,
`capi_market.json`, `capi_shipyard.json`, `capi_fleetcarrier.json`,
`capi_communitygoals.json`, and `fleet.json`.

---

### Default Grid Layout Updated

The default dashboard grid is updated for this release:

| Block | Col | Row | W | H |
|-------|-----|-----|---|---|
| commander | 0 | 0 | 8 | 14 |
| session_stats | 8 | 0 | 8 | 10 |
| crew_slf | 16 | 0 | 8 | 10 |
| missions | 0 | 14 | 8 | 9 |
| mode | 8 | 10 | 8 | 5 |
| cargo | 8 | 15 | 8 | 10 |
| engineering | 8 | 25 | 8 | 10 |
| alerts | 0 | 23 | 8 | 10 |
| assets | 16 | 10 | 8 | 25 |

Commander height increased by 1 row to accommodate the new squadron line.

---

### Upgrading

Delete `~/.local/share/EDMD/layout.json` to apply the new default grid. If you
prefer to keep your current layout, add the `mode` block manually if it is
missing.

After first launch, dock at any station to trigger a CAPI poll and write
`capi_profile.json`. From the second launch onward, full fleet data with
loadouts is available immediately on startup.

No `config.toml` changes required.

---

### Known Limitations

- Hardpoint localised names: some newer and named/special hardpoints
  (`mkiiplasmashockautocannon`, rare variants) resolve via the normaliser rather
  than CAPI `nameLocalized` — names are correct but formatting may differ
  slightly from in-game. Coverage is ongoing.
- Stored ship modules are sourced from accumulated journal `Loadout` events.
  If a ship has not been boarded since EDMD was installed, its loadout will be
  absent until it is boarded once.
- CAPI `/profile ships{}` does not include module data for stored ships
  (Frontier API limitation). Journal loadout events remain the only source.
- GTK4 GUI is Linux-native; Windows and macOS are best-effort.
- SLF shield state is not tracked.
- Block collapse state is not persisted across restarts.
