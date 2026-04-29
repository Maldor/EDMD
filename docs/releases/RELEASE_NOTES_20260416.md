# EDMD Release Notes

---

## 20260416

**Elite Dangerous Monitor Daemon — EDMD**

Major data architecture refactor, comprehensive three-UI standardisation pass,
Colonisation block rewritten as a Raven Colonial integration, bug fixes across
GTK4 / TUI / Electron covering carrier cargo value, home system distance,
commander block label corruption, and mission stack data. GitHub Actions
workflow updated to Node.js 24 throughout.

---

### Refactor — Shared Data Package

All inline reference maps previously scattered across `core/state.py`,
`components/assets/plugin.py`, and `gui/blocks/assets.py` are consolidated
into a new top-level `data/` package. This is purely an internal architectural
change — no user-visible behaviour changes.

**New modules:**

| Module | Contents |
|---|---|
| `data/ranks.py` | Rank name arrays and CAPI rank skill definitions |
| `data/ships.py` | Ship display name map, fighter type and loadout names, normalisation helpers |
| `data/modules.py` | Module type, class, mount, and size maps; `normalise_module_name()` |
| `data/engineering.py` | Blueprint and experimental effect name maps; `normalise_eng_name()` |
| `data/status_flags.py` | All `Flags`, `Flags2`, and `GuiFocus` bit constants |

`core/state.py` re-exports all names from `data/` so any code importing them
from `core.state` continues to work without changes.

**Bug fixed during refactor:** `normalise_module_name()` was applying the
internal slot size map (`large` → `3`) to hardpoint size labels, producing
`"3 Pulse Laser (Turret)"` instead of `"Large Pulse Laser (Turret)"`.
Hardpoint sizes now use title-case directly.

---

### Feature — Colonisation: Raven Colonial Integration

The colonisation plugin has been completely rewritten as an integration with
[Raven Colonial](https://ravencolonial.com) — a community tool for tracking
colonisation construction projects. Local tracking of construction site resource
requirements and delivery progress is unchanged. When a Raven Colonial API key
is configured, supply needs and commander contributions are synced to the site
in real time, so other commanders can see your project's live status.

> **Note:** Colonisation support remains experimental and under active
> development. API behaviour and journal schema coverage may change.

**Configuring Raven Colonial:**
Set your API key via **Preferences → Data → Raven Colonial API Key**, or add
it directly to `config.toml`:

```toml
[Colonisation]
ApiKey = "your-api-key-here"
```

Obtain your API key from [ravencolonial.com](https://ravencolonial.com) →
Account Settings. The API key can be changed at runtime without restarting EDMD.
Leave blank to use local tracking only.

---

### Enhancement — Block Standardisation (all three UIs)

A full audit and standardisation pass was completed across GTK4, Textual TUI,
and Electron interfaces. All three UIs now present identical data fields in
identical order within each block.

**Colonisation block** — Electron was showing a minimal progress-bar view with
only the top four resources and no cargo cross-reference. All three UIs now
show the full resource list sorted by most-needed first, `N needed (M in hold)`
framing when docked with matching cargo, a `▶` indicator for the currently
docked site, and a right-aligned `Total remaining: N t` footer row.

**Crew/SLF block** — Electron row order corrected from
`Hired → Active → Paid → SLF` to `SLF → Hired → Active → Paid`, matching
GTK4 and TUI.

**Session Stats block** — Electron Summary tab now shows `Duration` as its
first content row, matching GTK4 and TUI (previously Duration appeared only
in the panel header).

**Career block — TUI** — Several fields were missing from the detail tabs:
- *Combat:* Assassinations, Rebuy costs
- *Exploration:* Hyperspace jumps, Planets FSS, First footfalls, Highest payout;
  distance now uses `Total_Hyperspace_Distance` (was `Greatest_Distance_From_Start`)
- *Exobiology:* Species found, Genus found, Systems, Planets, First logged,
  First logged profits
- *Trade:* Resources traded, Mission income
- *PowerPlay:* Power and Rank rows, by-system merit breakdown

**Assets block — Cargo alpha sort** — Cargo items now sort alphabetically in
all three UIs with no category grouping.

**Mission stack** — Stack height row now shows kills and total credit value on
a single row (`kills | credits`) in all three UIs, matching GTK4.

---

### Fix — Commander Block: Shields Labeled "Hull"

In GTK4, the `Shields` key label was being overwritten with `"Hull"` on every
refresh. The cause was `get_first_child()` on the grid container returning the
Shields key label (the first widget in DOM order) rather than the Hull key
label. Fixed by storing `self._cmdr_hull_key` and `self._cmdr_shields_key`
explicitly at build time. `_kv()` now returns `(value_label, key_label)`.

TUI fixed via `KVRow.set_key()`. Electron was already correct via a computed
`hullLabel` property.

---

### Fix — Commander Block: Home System Distance Not Showing

Home system distance was never displayed because `_star_pos_live` was only set
to `True` on `FSDJump` events outside preload. The `Location` event, which
fires at login and always reflects the player's actual current position (not a
historical jump replay), now unconditionally sets `_star_pos_live = True`.
Distance is computed from live coordinates and displayed immediately on login.

---

### Fix — Assets Block: Fleet Carrier Cargo Value Always Zero

`FCMaterials.json` uses `"stock"` as the quantity key, not `"qty"`. The carrier
cargo value calculation was reading `m.get("qty", 0)` everywhere, producing zero
in all cases. Fixed in the GTK4 assets block (two locations) and the Electron
bridge serialiser.

---

### Fix — Colonisation Block: Total Remaining Alignment

In GTK4, the `Total remaining: N t` line was a standalone left-aligned label
appended below the resource grid. It now attaches inside the shared `Gtk.Grid`
as a proper key/value row so the tonnage value right-aligns with all other
resource values. TUI was already correct (uses `KVRow`). Electron updated to
share the same flex layout as resource rows.

---

### Fix — Mission Stack: Stale Missions Surviving Restart

When `state.missions` was truthy on storage restore, the reconciliation loop
in the Missions event handler was skipped entirely due to an over-broad guard
condition. Stale missions from previous sessions could survive indefinitely.
Fixed: reconciliation now runs unconditionally on every `Missions` event,
pruning entries not present in the live active mission list.

---

### Fix — Cargo: Category Field Removed

The cargo enrichment pipeline computed a category field that was no longer used
after the alpha-sort change removed category grouping. The field is removed from
`components/cargo/plugin.py`'s `get_electron_data()` and from the TUI cargo
block's enrichment dict. The unused `SecHdr` import is removed from
`tui/blocks/cargo.py`.

---

### Fix — GTK4 Cargo: `_get_spansh()` Pattern

`gui/blocks/cargo.py`'s `_get_spansh()` helper was using
`self.core.plugin_call.__self__._plugins.get("spansh")` — an internal
implementation detail. Replaced with `self.core._plugins.get("spansh")`,
matching every other block.

---

### Enhancement — CI/CD: GitHub Actions Updated to Node.js 24

All GitHub Actions are updated to versions that natively declare Node.js 24,
eliminating the Node.js 20 deprecation warnings that appeared in every workflow
run since September 2025. The `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` workaround
environment variable is removed as it is no longer required.

| Action | Old | New |
|---|---|---|
| `actions/checkout` | `v4.2.2` | `v6` |
| `actions/setup-node` | `v4.4.0` | `v6` |
| `actions/upload-artifact` | `v4` | `v6` |
| `actions/download-artifact` | `v4` | `v7` |

---

### Files Changed

| File | Change |
|---|---|
| `data/__init__.py` | New package |
| `data/ranks.py` | Rank name arrays and CAPI skill definitions |
| `data/ships.py` | Ship name map, fighter type/loadout names, normalisation helpers |
| `data/modules.py` | Module maps; `normalise_module_name()` hardpoint size fix |
| `data/engineering.py` | Blueprint and experimental effect maps |
| `data/status_flags.py` | All Flags/Flags2/GuiFocus constants |
| `core/state.py` | Imports and re-exports from `data/`; removes inline maps |
| `core/config.py` | `CFG_DEFAULTS_COLONISATION`; `colonisation_cfg` property |
| `core/electron_bridge.py` | `colonisation_cfg` in `get_prefs`; `colonisation` section in `save_prefs`; carrier cargo `stock` fix; `in_cargo` and `is_current` in colonisation serialiser |
| `components/assets/plugin.py` | Imports from `data/modules` and `data/engineering` |
| `components/cargo/plugin.py` | `category` field removed from `get_electron_data()` |
| `components/colonisation/plugin.py` | Full rewrite — Raven Colonial API integration; `get_electron_data()` adds `in_cargo` and `is_current` per site |
| `components/missions/plugin.py` | Reconciliation guard removed; always prunes stale missions |
| `components/commander/plugin.py` | `Location` always sets `_star_pos_live`; `FSDJump` preload guard unchanged |
| `gui/blocks/assets.py` | Carrier cargo `qty` → `stock` (two locations) |
| `gui/blocks/cargo.py` | `_get_spansh()` pattern corrected |
| `gui/blocks/colonisation.py` | Total remaining moved inside grid for right-aligned value |
| `gui/blocks/commander.py` | `_kv()` returns `(value, key)`; `_cmdr_hull_key` stored; hull label rename fixed |
| `gui/blocks/missions.py` | Stack height row consolidates kills and credits |
| `gui/preferences.py` | Raven Colonial API key field added |
| `tui/blocks/cargo.py` | Alpha sort; no categories; `SecHdr` import removed; `cat` field removed |
| `tui/blocks/career.py` | All missing detail tab fields added; `Total_Hyperspace_Distance` field corrected |
| `tui/blocks/commander.py` | Hull key label renamed via `KVRow.set_key()` |
| `tui/blocks/missions.py` | Stack height row consolidates kills and credits |
| `tui/preferences.py` | Raven Colonial API key field added; theme crash fix |
| `electron/renderer/src/components/CareerBlock.vue` | Trade tab Resources traded row confirmed present |
| `electron/renderer/src/components/ColonisationBlock.vue` | Full rewrite to match GTK4/TUI data layout |
| `electron/renderer/src/components/CrewSlfBlock.vue` | Row order corrected; standalone hull bar removed |
| `electron/renderer/src/components/MissionsBlock.vue` | Stack height row consolidates kills and credits |
| `electron/renderer/src/components/PreferencesPanel.vue` | Raven Colonial API key field added |
| `electron/renderer/src/components/SessionStatsBlock.vue` | Duration added as first Summary content row |
| `.github/workflows/release.yml` | All actions updated to Node.js 24 native versions |

---

**Full changelog:** see commit history on the `electron` branch.
**Verification:** download `EDMD-20260416.sha256` and the corresponding `.sha256.sig` and verify with `ssh-keygen -Y verify`.
