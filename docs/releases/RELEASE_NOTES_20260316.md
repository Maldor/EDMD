# EDMD Release Notes

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
