# EDMD Release Notes

---

## 20260406

**Elite Dangerous Monitor Daemon — EDMD**

Major feature and bug-fix release. Introduces a full Textual terminal UI as an
alternative to the GTK4 GUI — same layout, same data, no GTK4 required.
Resolves a ghost-crew display bug, at-risk holdings double-counting on restart,
ghost ships accumulating in the fleet, and session-stats reset timing. Fixes
CAPI authentication to show the commander's in-game name instead of the
Frontier account holder's real name. Bundles JetBrains Mono font and moves the
default layout to the version 2 grid.


---

> ### ⚠ REQUIRED: `config.toml` must be updated before launching this release
>
> The configuration section for the graphical interface has been **renamed and
> restructured**. EDMD will silently ignore the old `[GUI]` section — if you
> do not update your config, the GUI and TUI will not launch and EDMD will
> appear to fall back to terminal-only mode with no error message.
>
> **This affects every user who has `[GUI]` in their `config.toml`.**

---

### Config Migration — `[GUI]` → `[UI]`

#### Global section

| Old (`[GUI]`)              | New (`[UI]`)                       |
|----------------------------|------------------------------------|
| `Enabled = false`          | `Mode = "terminal"` *(or omit)*    |
| `Enabled = true`           | `Mode = "gtk4"`                    |
| *(no equivalent)*          | `Mode = "textual"`  *(new: TUI)*   |
| `Theme = "default"`        | `Theme = "default"`                |
| `FontFamily = "..."`       | `FontFamily = "..."`               |
| `FontSize = 14`            | `FontSize = 14`                    |
| `SoftwareRenderer = false` | `SoftwareRenderer = false`         |

Replace the entire `[GUI]` block in your config with `[UI]`:

```toml
# BEFORE
[GUI]
Enabled          = true
Theme            = "default-green"
FontFamily       = "JetBrains Mono"
FontSize         = 14
SoftwareRenderer = false

# AFTER
[UI]
Mode             = "gtk4"           # gtk4 | textual | terminal
Theme            = "default-green"
FontFamily       = "JetBrains Mono"
FontSize         = 14
SoftwareRenderer = false
```

#### Profile sections

Profile-level GUI overrides follow the same rename. Replace `GUI.*`
keys with `UI.*`:

```toml
# BEFORE
[REMOTE]
GUI.Enabled = false

[EDP1]
GUI.Theme    = "default-green"
GUI.FontSize = 14

# AFTER
[REMOTE]
UI.Mode  = "textual" 
UI.Theme = "default"

[EDP1]
UI.Mode     = "gtk4"
UI.Theme    = "default-green"
UI.FontSize = 14
```

#### Choosing a Mode

| Value | Launches |
|---|---|
| `"terminal"` | Terminal output only — no graphical window *(default if Mode is absent)* |
| `"gtk4"` | GTK4 graphical dashboard — requires PyGObject / GTK4 |
| `"textual"` | Textual terminal dashboard — no GTK4 required, works on any terminal |

The `Mode` key can be set globally or overridden per profile. The `--mode`
CLI flag always takes precedence over the config file.

#### No other keys changed

`[Settings]`, `[Discord]`, `[LogLevels]`, and all integration sections
(`[EDDN]`, `[EDSM]`, `[EDAstro]`, `[Inara]`) are unchanged. Profile keys
within those sections are unchanged. Only the `[GUI]` → `[UI]` rename and
the `Enabled` → `Mode` substitution require action.

---

### Feature — Textual TUI Mode

A complete terminal dashboard is now available alongside the existing GTK4 GUI.
Launch with `--mode textual` (or select the **EDMD (TUI)** shortcut on
Windows). No GTK4, GObject, or MSYS2 is required — the TUI runs on any system
with Python 3.11+ and a modern terminal emulator.

#### Dashboard layout

Three columns (34 % / 34 % / 32 %) with ten information blocks whose
proportions are hardcoded to match `layout.json`:

| Column | Blocks |
|---|---|
| Left | Career · Session Stats · Colonisation |
| Centre | Commander · Alerts · Mission Stack · Cargo |
| Right | Crew/SLF · Assets · Engineering |

Each block uses left-aligned keys and right-aligned values via `KVRow` widgets,
matching the GTK4 visual convention. Tabs with internal scroll handle overflow;
the outer frame never scrolls.

#### Theme support

All eight built-in EDMD palettes are supported: Default, Default Dark, Default
Green, Default Blue, Default Purple, Default Red, Default Yellow, Default Light.
Custom CSS themes from `themes/custom/` are discovered automatically. Theme
selection applies a live preview immediately and saves to config on Apply.

#### Preferences screen (Ctrl+O)

A full-screen `ModalScreen` with five tabs mirroring the GTK4 preferences
dialog exactly:

- **General** — journal folder, UTC timestamps, display toggles, inactivity
  alert thresholds
- **Notifications** — per-event log levels (0–3) via `Select` dropdowns with
  labels: Off / Terminal / + Discord / + Ping
- **Discord** — webhook URL, user ID, all five option toggles
- **Appearance** — theme selection with immediate preview
- **Data & Integrations** — Frontier CAPI connect/disconnect with live auth
  status, EDDN, EDSM, EDAstro, and Inara enable/credential settings

Changes write to the active profile section (`[EDP1.Section]`) or global
section, matching GTK4 behaviour exactly. Hot-reloadable settings take effect
immediately; restart-required settings trigger `os.execv` with the original
launch arguments.

#### Reports screen (r)

All eight statistical reports from `core/reports.py` are accessible from a
`ModalScreen` sidebar. Reports run in a background thread; `app.call_from_thread`
delivers the result to the main event loop. Tabular sections render with
dynamic column widths and right-aligned numeric values.

| Report | Contents |
|---|---|
| Career Overview | Lifetime kills, credits, and time played |
| Bounty Breakdown | Kills and credits by ship type |
| Session History | Per-session summary table |
| Hunting Grounds | Most-visited systems and stations |
| NPC Rogues' Gallery | Unique attacker names and frequency |
| Exploration | Discovery and cartography statistics |
| Exobiology | Sample counts and sold totals |
| PowerPlay | Merit totals by system |

#### Keyboard bindings

| Key | Action |
|---|---|
| `ctrl+q` | Quit |
| `ctrl+r` | Reset session |
| `ctrl+l` | Clear alerts |
| `r` | Open Reports screen |
| `ctrl+o` | Open Options / Preferences |

(`ctrl+c` is deliberately not bound — it sends SIGINT in terminals before
Textual's raw-mode loop can reliably intercept it.)

#### Block highlights

- **Cargo** — galactic average pricing from the last docked market; no network
  calls. Item rows show `name | qty t | avg_price` with right-aligned values.
- **Session Stats** — summary and per-activity tabs rebuilt dynamically from
  providers using `KVRow` widgets; `TabPane` content is passed at construction
  to avoid a `NoMatches` race in Textual's `ContentSwitcher`.
- **Crew/SLF** — always visible in its allocated 28 % column height; shows "No
  NPC crew" placeholder when no crew is present so the fixed layout has no gap.
- **Assets** — four tabs: Wallet, Ships, Modules, Fleet Carrier. All metric
  rows use `KVRow`; Ships and Modules tabs use scrollable label lists.
- **Mission Stack** — wing-reward suffix removed; faction rows are `KVRow` with
  kill count left and reward + Δ-delta right.

---

### Fix — Crew/SLF: Ghost Crew Member (Lia Brady Bug)

After a second NPC crew member was hired, EDMD sometimes displayed that crew
member's name as the active pilot even when they had never been assigned.

**Root cause.** `NpcCrewPaidWage` events fire simultaneously for every hired
crew member in each pay cycle. The handler used a first-event fallback:
`if not state.crew_name and wage_name: state.crew_name = wage_name`. After a
`Loadout` event cleared `crew_name` to `None` (because the SLF type was
unknown), the next wage cycle's ordering was not guaranteed to put the correct
active crew member first. If the wrong name landed in `crew_name`, and no
`CrewAssign` event fired in the session, the stale name persisted indefinitely.

**Fix.** The `NpcCrewPaidWage` fallback is removed entirely. `crew_name` is
now set exclusively by `CrewAssign` events. A new `_bootstrap_crew_from_journals()`
method scans journals newest-first for the last `CrewAssign {Role: Active}`
event and restores `crew_name` authoritatively. It launches as a daemon thread
from the `Loadout` handler whenever crew state is reset, running alongside the
existing SLF-type bootstrap thread.

---

### Fix — Holdings: At-Risk Vouchers Double-Counted on Restart

After a restart, at-risk holdings (bounty vouchers, combat bonds, trade
vouchers) were sometimes double-counted because the deduplication set was not
persisted across sessions.

**Fix.** A `_seen_vouchers` set is now persisted to plugin storage alongside
the existing `_seen_exobio` set. On load, both sets are restored and applied
as deduplication filters before any journal events are processed. The pattern
mirrors the exobiology deduplication introduced in the previous release cycle.

---

### Fix — Fleet: Ghost Ships and Raw Type Names

Two related fleet display bugs.

**Ghost ships.** The CAPI fleet merge was additive — ships from previous CAPI
responses were kept even if they had disappeared from the fleet. Over time,
sold or otherwise removed ships accumulated in the displayed fleet.

**Fix.** CAPI data is now treated as the authoritative fleet state. On each
CAPI profile poll, the fleet is replaced entirely from the CAPI response rather
than merged into the existing state.

**Raw type names.** Ships loaded from persistence occasionally displayed
underscore-format internal type strings (e.g. `typex_3`) instead of their
localised names.

**Fix.** A sanitisation pass detects `type_display` values matching the
underscore pattern and replaces them with the localised name resolved from the
in-game ship name registry.

---

### Fix — Session Stats: Manual Reset Timing

Manually resetting the session (keyboard shortcut) did not always produce
correct timings for the new session because `_session_start_time` was not
updated until the next journal event.

**Fix 1.** `_session_start_time` is armed to `datetime.utcnow()` immediately
when the reset action fires, not deferred to the next event.

**Fix 2.** A `_reset_after` sentinel is persisted to storage. On restart, if
the sentinel is present and newer than the stored session start, the session is
reset before any journal events are processed. This ensures a reset that fired
just before a crash or restart takes effect correctly on the next startup.

---

### Fix — CAPI: Commander Name Shows In-Game Name

The Frontier CAPI OAuth token's `/decode` endpoint returns `usr.firstname` —
the account holder's real first name — rather than the in-game commander name.
Both the GTK4 preferences and TUI preferences were displaying this real-name
value in the "Connected — {name}" status line.

**Fix.** `auth_status()` and `commander_name()` in `core/data.py` now prefer
`state.pilot_name` — set from the game journal's `Commander` event, which
carries the actual in-game CMDR name — over the stored OAuth firstname. The
OAuth value is used only as a fallback before the first journal event of a
session has been processed. This fixes both the GTK4 and TUI preferences
displays with no change to the authentication flow.

---

### Feature — Bundled JetBrains Mono Font

JetBrains Mono is now bundled in `fonts/` and registered at startup via
PangoCairo, eliminating the need to install it separately.

`bootstrap_fonts()` in `gui/helpers.py` copies the TTF files to
`EDMD_DATA_DIR/fonts/` on first run and registers the family per-process using
`PangoCairo.font_map_get_default().load_fontconfig_font_from_file()`. Font
family and size are configurable in Settings → Appearance. GTK4 CSS injects
the selected font as a concrete rule rather than a CSS variable (GTK4 CSS does
not support `var()` for font-family).

---

### Default Layout: Version 2

The internal default layout and `example.layout.json` are updated to the
32-column × 10 px-row version 2 grid. Column widths are 11 : 11 : 10 (left :
centre : right). The new proportions align block boundaries more precisely with
the natural information density of each column.

---

### Windows: TUI Shortcuts Added

The Inno Setup installer now creates **EDMD (TUI)** start menu and desktop
shortcuts alongside the existing GTK4 shortcut. The TUI launcher passes
`--mode textual` and does not require GTK4 or MSYS2 at runtime. The bundled
Python runtime ships `textual` as a pip dependency.

---

### Files Changed

| File | Change |
|---|---|
| `core/state.py` | VERSION → 20260406 |
| `core/data.py` | `auth_status()` and `commander_name()` prefer `state.pilot_name` over OAuth firstname |
| `core/components/holdings/plugin.py` | `_seen_vouchers` deduplication set added; persisted to storage |
| `core/components/session_stats/plugin.py` | `_session_start_time` armed immediately on reset; `_reset_after` sentinel added |
| `core/components/assets/plugin.py` | CAPI fleet treated as authoritative (non-additive); `type_display` sanitisation pass |
| `core/components/crew_slf/plugin.py` | `_bootstrap_crew_from_journals()` added; `NpcCrewPaidWage` crew_name fallback removed; crew bootstrap thread launched from `Loadout` handler |
| `gui/helpers.py` | `bootstrap_fonts()` added; JetBrains Mono TTFs copied to data dir and registered via PangoCairo |
| `gui/grid.py` | DEFAULT_LAYOUT updated to version 2 (32-col × 10px-row) |
| `gui/preferences.py` | CAPI status now shows in-game CMDR name (inherits from `data.py` fix) |
| `fonts/` | JetBrains Mono TTF files added |
| `tui/` | New — complete Textual TUI implementation |
| `tui/app.py` | Application entry point; 10-block three-column layout; hotkey bindings |
| `tui/theme.py` | `build_css()` palette substitution; 8 built-in themes; custom theme support via `themes/custom/*.css`; `list_custom_themes()` |
| `tui/block_base.py` | `TuiBlock`, `KVRow`, `SepRow`, `SecHdr` base widgets |
| `tui/preferences.py` | Full preferences `ModalScreen`; five tabs; profile-aware config write-back; CAPI connect/disconnect |
| `tui/reports.py` | Reports `ModalScreen`; all 8 reports; background thread with `app.call_from_thread` delivery |
| `tui/blocks/alerts.py` | Alerts block |
| `tui/blocks/assets.py` | Assets block — Wallet, Ships, Modules, Fleet Carrier tabs |
| `tui/blocks/career.py` | Career block — Summary, Combat, Exploration, Exobiology, Mining, Trade, PowerPlay tabs |
| `tui/blocks/cargo.py` | Cargo block — galactic average pricing; dynamic `KVRow` rebuild |
| `tui/blocks/colonisation.py` | Colonisation block — construction site tracker with `KVRow` resource rows |
| `tui/blocks/commander.py` | Commander block — vessel, location, PowerPlay, crew info tabs |
| `tui/blocks/crew_slf.py` | Crew/SLF block — always visible; placeholder when no crew |
| `tui/blocks/engineering.py` | Engineering block — 7-tab materials inventory with dynamic `KVRow` rebuild |
| `tui/blocks/missions.py` | Mission Stack block — `KVRow` faction rows; wing-reward suffix removed |
| `tui/blocks/session_stats.py` | Session Stats block — dynamic `KVRow` rebuild per provider tab |
| `example.layout.json` | Updated to version 2 layout |
| `README.md` | TUI badge, feature row, `tui-screenshot.png`, Quick Start updated |
| `installer/EDMD.iss` | TUI start menu and desktop shortcuts added |
