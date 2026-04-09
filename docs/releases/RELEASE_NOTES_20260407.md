# EDMD Release Notes

---

## 20260407

**Elite Dangerous Monitor Daemon — EDMD**

TUI stabilisation, polish, and bug-fix release. Completes the Textual terminal
dashboard introduced in 20260406 with corrected block layouts, full price
display in the Cargo block, a generic search modal for home and target market
selection, and a fix for the idle kill alert firing during supercruise. Resolves
a Rich markup rendering bug that prevented squadron idents from displaying in the
TUI commander block despite the data being correct in state. Includes config
format self-healing that prevents preferences saves from silently reverting to
the old sub-table format.

---

> ### ⚠ REQUIRED: `config.toml` must be updated before launching this release
>
> The configuration section for the graphical interface was **renamed and
> restructured** in 20260406. EDMD will silently ignore the old `[GUI]` section.
> Starting with this release, EDMD will automatically migrate `[GUI]` → `[UI]`
> on first launch. Existing configs that have already been updated are unaffected.
>
> See the 20260406 release notes for the full before/after migration table.

---

### Fix — TUI: Squadron Ident `[XXXX]` Not Displaying

The commander block in TUI mode showed the squadron name and rank correctly but
never displayed the 4-character squadron ident (e.g. `[MALL]`). The underlying
data was correct in state at all times — the field `pilot_squadron_tag` was
being set to the correct value by both the startup disk read and every live CAPI
poll.

**Root cause:** Textual uses Rich markup for all Label content. Rich markup
treats `[` as the opening of a style tag. The string `"MASSIVE ASSET LOAD
LIFTERS [MALL]"` passed to `Label.update()` caused Rich to interpret `[MALL]`
as an unknown style tag and silently drop it from the rendered output. No
exception was raised. GTK4 is unaffected because Pango markup does not treat
`[` as a special character.

**Fix.** The ident is now formatted using the Rich escape sequence for a literal
bracket: `r" \["` + tag + `"]"`. Rich renders `\[MALL]` as the literal string
`[MALL]`. The same escaping pattern should be applied to any text containing
user-supplied bracket characters passed to Textual Labels.

---

### Fix — TUI: Session Stats Block Crash on Tab Switch

Switching between activity tabs in the Session Stats block occasionally raised:

```
NoMatches: No child found with id='ss-tab-exploration'
```

**Root cause.** The previous implementation added and removed `TabPane` widgets
dynamically during `refresh_data()`. Textual's `ContentSwitcher` registers pane
IDs at mount time. Removing a pane from the DOM while the `ContentSwitcher` held
a reference to its ID caused the switcher to raise `NoMatches` when the user
clicked a tab that had been removed and re-added in the same render cycle.

**Fix.** All ten activity tabs (`Summary`, `Combat`, `Exobio`, `Explore`,
`Income`, `Mine`, `Mission`, `Odyssey`, `PPlay`, `Trade`) are now pre-built as
static `TabPane` widgets at compose time with fixed IDs. `refresh_data()` only
ever repopulates the `VerticalScroll` content within each pane — the DOM
structure never changes after initial mount.

---

### Fix — Idle Kill Alert: False Positive During Supercruise

The inactivity alert ("No kills in N minutes") could fire while the commander
was actively travelling in supercruise between combat zones. The timer continued
counting while in supercruise because no kill can occur there.

**Fix.** The idle alert condition in `activity_combat/plugin.py` now includes
`and not getattr(state, "in_supercruise", False)`. The timer pauses whenever
`state.in_supercruise` is `True`, matching the existing preload guard in the
same check.

---

### Fix — Config: Preferences Save Reverting to Old Sub-Table Format

Every time preferences were saved from either the GTK4 or TUI preferences
screen, the config was silently written back in the old `[ProfileName.Section]`
sub-table format — the same format that the config migration was designed to
eliminate. This reversed any migration that had been applied.

**Root cause.** Both `gui/preferences.py` and `tui/preferences.py` contained a
local `_dict_to_toml()` function that always wrote the old format.

**Fix.** A single canonical `config_to_toml()` function in `core/config.py` now
owns all config serialisation. Both preferences files import and call it.
Standard sections (`Settings`, `Discord`, `UI`, `LogLevels`, etc.) are written
as flat `[Section]` tables. Profile sections are written as a single
`[ProfileName]` header with dotted sub-keys (`Settings.JournalFolder = ...`,
`UI.Mode = ...`). The local `_dict_to_toml` is removed from both preferences
files.

A startup migration — `migrate_config_if_needed()` in `core/config.py`, called
from `edmd.py` before `load_config_file` — rewrites any file still using the
old format, including `[GUI]` → `[UI]` conversion and `Enabled = true` →
`Mode = "gtk4"` substitution.

---

### Fix — TUI Cargo: No Price Estimates Displayed

The cargo block showed item names and tonnage but never displayed galactic
average prices, even when the commander had recently docked at a market.

**Root cause.** The block only rendered a price column when both `has_prices`
(market data loaded) and `avg > 0` (item has a non-zero mean price) were true.
Mission cargo and collectible items (Agronomic Treatment, Guardian Relics, etc.)
are not listed on the commodity market, so their `mean_price` is always 0 —
causing the entire price column to be skipped for those items, and collapsing
the block when only mission cargo was present.

**Fix.** The price column is now always rendered, showing `—` when no price is
available for a specific item. Price priority: target station sell price →
last-docked market sell price → galactic average. The block header right-aligns
a label showing the active price source: the selected target station (if one
is set), the last docked market name, or `Gal. Avg`.

---

### Fix — Cargo: Target Station System Name Dropped

When selecting a target market via the search modal, the system name was not
saved alongside the station name — the display showed `StationName |` with
a missing system.

**Root cause.** `spansh.search()` returns results with the system under the key
`"system"` (normalised from `rec["system_name"]`). But `spansh._store_record()`
read only `rec.get("system_name", "")`, which returns `""` when the result came
in via the `_record=` fast path that bypasses a second network fetch.

**Fix.** `_store_record` now reads `rec.get("system_name") or rec.get("system")`,
covering both the raw Spansh record format and the pre-normalised search result.

---

### Feature — TUI: Commander Block Header Redesign

The commander block header is restructured to display two lines of identity
information before the tab strip:

```
CMDR TESS TEACLE - CORAX - TT-EXP (MANDALAY)
EXECUTIVE DIRECTOR - MASSIVE ASSET LOAD LIFTERS [MALL]
```

- **Line 1** — Commander name and vessel context. Format varies by mode:
  - In ship: `CMDR {name} - {ship-name} - {ident} ({ship-type})`
  - On foot: `CMDR {name} - {suit-loadout} ({suit-type})`
  - In SRV: `CMDR {name} - {srv-type}`
  - In fighter: vessel info + `[IN FIGHTER]` suffix
- **Line 2** — Squadron identity: `{RANK} - {SQUADRON NAME} [{TAG}]`

Both lines use the `block-title` CSS class (accent colour, title-bar background).
The green separator sits after line 2, above the tab strip. No separate
"COMMANDER" block title label is rendered — the header IS the title.

---

### Feature — TUI: Crew/SLF Block Header Redesign

The `CREW / SLF` block title label is replaced by a single-row Horizontal
containing two Labels: crew name left-aligned (accent, bold) and SLF type
right-aligned. The crew's combat rank appears on a second title-bar line below.
When no crew is present, the first row shows `No NPC crew` with the SLF slot
empty.

---

### Feature — TUI: Search Modals for Home Location and Target Market

Two `>> Set Home` / `>> Set Target` footer strips are added to the Commander
and Cargo blocks respectively. Clicking either opens a `SearchModal` —
a generic `ModalScreen` parameterised by title, placeholder, Spansh search
function, result formatter, and selection callback.

The modal debounces input by 400 ms, runs the search on a background thread,
and displays results as pressable buttons. Pressing a result calls the callback
and dismisses the modal. Press `Escape` to cancel.

- **Set Home** calls `commander_plugin.set_home_location(name, system, star_pos)`
- **Set Target** calls `spansh.set_target(name, system, _record=result)`,
  which stores the full station market data and triggers a cargo block refresh

---

### Enhancement — TUI: Block Spacing and Alignment

Section headers throughout the TUI no longer have a blank line above them.
`SecHdr.DEFAULT_CSS` `margin-top` changed from `1` to `0` globally, and
`STRUCTURAL_CSS` overrides are removed. The change eliminates wasted rows in
every block that uses section headers, reclaiming that space for data.

`SepRow` is now zero-height (invisible) everywhere in the TUI. Visual
separation between logical sections is provided by `SecHdr` labels, which
carry sufficient contrast via the accent colour and bold style without consuming
an additional row.

---

### Enhancement — TUI: Career Block

Summary tab now uses `SecHdr` + individual `KVRow` widgets per activity
(Combat → Kills / Bounties, Exploration → Systems / Cartography, etc.) rather
than a monolithic Label. This produces proper left/right column alignment
consistent with all other blocks.

Tab labels shortened to fit the tab bar without overflow: Summary / Combat /
Explore / Exobio / Mine / Trade / PPlay.

---

### Enhancement — TUI: Session Stats Block

Summary tab uses the same `SecHdr` + `KVRow` pattern as Career Summary.
Each active provider contributes a `SecHdr(title)` followed by its data rows.

Tab labels match Career style for visual consistency: Summary / Combat / Exobio
/ Explore / Income / Mine / Mission / Odyssey / PPlay / Trade.

---

### Enhancement — TUI: Mission Stack Block

Faction rows now render in aligned two-column format:

```
Active                      7/20  |    179.9M
Monarchy of Votama           118  |    103.3M
Eagle Corporation Industries  77  |     76.6M
──────────────────────────────────────────────
Stack height                 118
```

- Kill/mission count right-padded to 5 characters (bright)
- `|` separator (dim)
- Credit value right-padded to 8 characters (dim)
- Dim `─` separator line above the stack height row
- Stack height column-aligned with kill counts above it

The Δ stack-delta column is removed.

---

### Enhancement — TUI: Assets Block

**Ships tab** now uses `KVRow` widgets to display ship name and ident on the
left with docked location (`Station  (System)`) right-aligned. The `▶ CURRENT`
indicator is retained. Ship monetary value is kept in state but not displayed.

**Modules tab** now uses `SecHdr` per storage system and `KVRow` per module,
giving right-aligned credit values consistent with all other blocks. Previously
used flat text lines with no column alignment.

---

### Enhancement — TUI: Cargo Block Layout

The cargo block total row now renders in the same fixed-width column format as
item rows:

```
OTHER
  Agronomic Treatment     3 t  |         —
  Guardian Relic          5 t  |         —
Totals                    8 t  |         —
```

The label `"Totals"` matches the GTK4 UI. When no price data is available for
a given item, the credit column shows `—` rather than being omitted. The target
station name is shown in the block header right side, replacing `Gal. Avg` when
a station is selected.

---

### Enhancement — TUI: Theme Accuracy

All eight TUI palette accents now exactly match their GTK4 counterparts:

| Theme | Accent |
|---|---|
| default / default-dark | `#e07b20` (Elite orange) |
| default-green | `#00aa44` |
| default-blue | `#3d8fd4` |
| default-purple | `#9b59b6` |
| default-red | `#cc3333` |
| default-yellow | `#d4a017` |

The `default` and `default-green` themes now carry full hue tinting across
all backgrounds, borders, and dim text — matching the visual depth of the
existing red, yellow, blue, and purple themes.

---

### Files Changed

| File | Change |
|---|---|
| `core/state.py` | VERSION → 20260407 |
| `core/config.py` | `config_to_toml()` canonical writer; `migrate_config_if_needed()` startup migration; `STANDARD_SECTIONS` constant |
| `core/data.py` | Squadron tag extraction tries all known field name casings; OAuth firstname fallback kept for pre-journal sessions |
| `core/components/assets/plugin.py` | Squadron tag extraction uses all-casing fallbacks; commander block refresh triggered after squadron state write |
| `core/components/spansh/plugin.py` | `_store_record` reads `system_name` or `system` field for station system |
| `builtins/activity_combat/plugin.py` | `in_supercruise` guard added to idle alert condition in `tick()` |
| `gui/preferences.py` | Local `_dict_to_toml` removed; imports `config_to_toml` from `core.config` |
| `tui/app.py` | `cmdr_update` and `capi_updated` added to `_MSG_DISPATCH`; `capi_updated` refreshes commander, crew, assets, cargo |
| `tui/block_base.py` | `SecHdr.margin-top` → 0; `SepRow` zero-height; `HdrRow` widget added; `KVRow.set_key()` added |
| `tui/theme.py` | All accent colours corrected to match GTK4; `default` and `default-green` full background tinting; footer label CSS; search modal CSS; crew header CSS; section spacing fixes |
| `tui/search_modal.py` | New — generic search-and-select `ModalScreen` |
| `tui/preferences.py` | All `Switch` widgets replaced with `Select(Off/On)`; imports `config_to_toml` from `core.config` |
| `tui/reports.py` | `app.call_from_thread` used throughout; `try/except BaseException` + `finally` guarantees UI update |
| `tui/blocks/commander.py` | Two-line header (vessel line + squadron line); Rich markup escape for `[TAG]`; `>> Set Home` footer; reads same state fields as GTK4 block |
| `tui/blocks/crew_slf.py` | Horizontal name/type header row; rank on second title-bar line |
| `tui/blocks/career.py` | SecHdr + KVRow summary layout; shortened tab labels |
| `tui/blocks/session_stats.py` | Pre-built static tabs (fixes NoMatches crash); SecHdr + KVRow summary layout; consistent tab labels |
| `tui/blocks/assets.py` | Ships show location via KVRow; modules use KVRow for right-aligned values; all SepRows removed |
| `tui/blocks/missions.py` | Fixed-width count\|credit columns; dim separator above stack height; Δ removed |
| `tui/blocks/cargo.py` | Always-visible price column; price source header label; `>> Set Target` footer; Totals row with — placeholder |
