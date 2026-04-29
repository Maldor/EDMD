# EDMD Release Notes

---

## 20260409

**Elite Dangerous Monitor Daemon — EDMD**

Major structural refactor consolidating all application components into a single
flat `components/` directory, GTK4 removed from Windows entirely in favour of
TUI and terminal modes, Windows process restart hardened against terminal
corruption, idle kill alert redesigned around a single authoritative state
field, and a comprehensive TUI polish pass covering block header alignment,
block height redistribution, and the update notice banner.

---

### Refactor — Unified `components/` Directory

All application components previously spread across `core/components/`,
`builtins/`, and the root now live in a single flat `components/` directory.

**What moved:**

| Old path | New path |
|---|---|
| `core/components/alerts/` | `components/alerts/` |
| `core/components/assets/` | `components/assets/` |
| `core/components/cargo/` | `components/cargo/` |
| `core/components/commander/` | `components/commander/` |
| `core/components/crew_slf/` | `components/crew_slf/` |
| `core/components/engineering/` | `components/engineering/` |
| `core/components/missions/` | `components/missions/` |
| `core/components/session_stats/` | `components/session_stats/` |
| `core/components/spansh/` | `components/spansh/` |
| `builtins/activity_combat/` | `components/combat/` |
| `builtins/activity_exobiology/` | `components/exobiology/` |
| `builtins/activity_exploration/` | `components/exploration/` |
| `builtins/activity_income/` | `components/income/` |
| `builtins/activity_mining/` | `components/mining/` |
| `builtins/activity_missions/` | `components/missions_session/` |
| `builtins/activity_odyssey/` | `components/odyssey/` |
| `builtins/activity_powerplay/` | `components/powerplay/` |
| `builtins/activity_trade/` | `components/trade/` |
| `builtins/catalog/` | `components/catalog/` |
| `builtins/colonisation/` | `components/colonisation/` |
| `builtins/edastro/` | `components/edastro/` |
| `builtins/eddn/` | `components/eddn/` |
| `builtins/edsm/` | `components/edsm/` |
| `builtins/holdings/` | `components/holdings/` |
| `builtins/inara/` | `components/inara/` |
| `builtins/journal_history/` | `components/journal_history/` |
| `builtins/session_manager/` | `components/session_manager/` |

The `activity_` prefix is stripped from all former activity component
`PLUGIN_NAME` values. `activity_missions` is renamed `missions_session` to
distinguish it from the data-authority `missions` component. The `builtins/`
directory is removed entirely.

`core/plugin_loader.py` `load_all()` now performs a single flat scan of
`components/` with no subdirectory recursion. Integration components (`eddn`,
`edsm`, `edastro`, `inara`) remain user-togglable. All others are always-on.

---

### Refactor — Architectural Separation: Data vs Session Aggregation

The component set is now cleanly divided into two roles:

**Data components** own journal-driven state, emit notifications, and persist
to storage: `alerts`, `assets`, `cargo`, `catalog`, `colonisation`, `commander`,
`crew_slf`, `eddn`, `edsm`, `edastro`, `engineering`, `holdings`, `inara`,
`journal_history`, `missions`, `session_manager`, `spansh`.

**Session aggregators** implement `ActivityProviderMixin`, register as session
providers, maintain only ephemeral session-scoped counters, and reset on session
reset: `combat`, `exobiology`, `exploration`, `income`, `mining`,
`missions_session`, `odyssey`, `powerplay`, `trade`.

`ActivityProviderMixin` gains a shared `_duration_seconds()` implementation
(using `datetime.now(timezone.utc)` for live wall-clock duration), removing
identical copy-pasted implementations from `combat`, `income`, `powerplay`,
`trade`, and `missions_session`.

---

### Refactor — Combat: Notification Ownership Clarified

The `handle_event` function in `core/journal.py` operates in two code paths:
a new plugin-dispatch path (active when `plugin_dispatch` is provided) and a
legacy path. The legacy path is never reached in normal operation; all
`emitter.emit()` calls for kills, deaths, and other notifications that
previously lived there are now correctly owned by the components that hold
the relevant counters and context.

`combat` now carries `SUBSCRIBED_EVENTS = ["Bounty", "FactionKillBond", "Died",
"FighterDestroyed"]` and emits formatted kill and death notifications directly
from `on_event`. This is the correct architectural home: combat has the kill
count, interval timing, faction tally, ship tally, and config flags needed to
produce the full notification string.

---

### Fix — Windows: Terminal Corruption on TUI Restart

Applying settings from TUI preferences on Windows previously caused two EDMD
processes to run simultaneously: `os.execv` spawns a child on Windows instead
of replacing the parent, leading both instances to write interleaved ANSI
escape sequences to the terminal.

**Fix — sentinel file pattern.** Before calling `app.exit()`, the preferences
screen writes `%TEMP%\edmd_restart_{pid}.sentinel` and registers `atexit` to
delete it on clean exit. A non-daemon thread polls until the sentinel disappears
(meaning the old process has fully exited and the terminal is restored), then
waits an additional 150 ms buffer before spawning the new process. `edmd.py`
startup scans for stale sentinels and waits up to 3 seconds for them to clear
before initialising Textual's raw terminal mode.

**Fix — cmd.exe detection.** `edmd_launcher.exe` uses `psutil` to check whether
its parent process is `cmd.exe`. If so, it relaunches itself inside
`powershell.exe -NoExit` and exits the cmd-spawned instance. cmd.exe has
incomplete mouse-tracking support that causes visual glitches with Textual.
PowerShell is always used when launched from cmd.

---

### Fix — Idle Kill Alert Redesigned

The inactivity alert had multiple independent timers across `journal.py` and
`activity_combat` that could drift and cause spurious or missed alerts.

**New design.** A single field `state.last_kill_mono: float` on `MonitorState`
is the sole source of truth for when the last live kill occurred.
`journal.py` writes it on every `Bounty`/`FactionKillBond` event that is not
preload, and resets it to `time.monotonic()` on every `LoadGame`. The combat
component's `tick()` reads only this field — no fallback timers, no
`_last_summary_mono`, no `WarnNoKillsInitial`. The `on_summary()` hook is
removed. `WarnNoKillsInitial` config key is retired.

---

### Fix — TUI: Update Notice Banner

A version-available notice bar is now rendered between the Textual `Header` and
the dashboard. It starts at `height: 0` (takes no space). When `update_notice`
arrives on the queue, the bar is set to `height: 1` and displays the available
version and a link to the releases page in bold yellow. The bar uses Python-driven
height toggling — Textual does not support `:not(:empty)` CSS pseudo-class.

---

### Fix — TUI: Block Header Alignment

Block title labels previously rendered with a leading and trailing space
(`f" {self.BLOCK_TITLE} "`), producing two characters of left indent due to the
combination of the space literal and CSS `padding: 0 1`. Commander and Crew
blocks, which used plain string labels, aligned at one character. All blocks
now use `Label(self.BLOCK_TITLE)` with CSS padding providing the sole indent,
giving uniform alignment across the entire dashboard. The Cargo block's
hardcoded `" CARGO "` string is corrected to `"CARGO"` separately.

---

### Enhancement — TUI: Crew/Assets/Engineering Height Redistribution

The Crew/SLF block displays at most 6 rows of content (2 header + 4 data).
Its height is reduced from 28% to 18% of the right column. The reclaimed 10
percentage points are distributed equally: Assets grows from 40% to 45%,
Engineering from 32% to 37%.

---

### Enhancement — TUI: Assets Block Wallet — Carrier Parity with GTK4

The wallet tab now includes a **Fleet Carrier** section with two rows:

- **Hull (decom.)** — fixed decommission return value: 4.85 B for standard
  carriers, 24.85 B for squadron carriers. Hidden when no carrier is detected.
- **Cargo** — galactic average value of all FC materials on board.

**Net worth** now uses `assets_total_wealth` from the `Statistics` journal
event when available, adding carrier cargo value, at-risk holdings, and carrier
hull value on top — matching the GTK4 calculation exactly. Previously, net
worth was computed from a simple sum of balance + ships + modules + holdings,
missing carrier value and cargo.

---

### Enhancement — TUI: Preferences — EDAstro Integration Tab

Confirmed present and complete: the Data tab includes Enable and Include Carrier
Events fields for EDAstro, matching GTK4 parity. No change required.

---

### Fix — TUI: Alerts Block Scrollbar

The Alerts block used `VerticalScroll` to contain its five fixed-height alert
rows. `VerticalScroll` activates its scrollbar indicator when content height
approaches container height, producing a visible scroll affordance even when
there is nothing to scroll. Since the block always contains exactly `_MAX_ROWS`
pre-built `Label` widgets with no dynamic addition or removal, the container is
changed to a plain `Vertical`. The scrollbar is eliminated.

---

### Fix — `alerts` Component: Missing `Repair` Subscription

The `alerts` component handled the `Repair` journal event (individual hull or
component repair at a station, which resets `state.ship_hull` to 100) but did
not include it in `SUBSCRIBED_EVENTS`. The event was never dispatched to the
component, leaving hull state stale until the next `Loadout` event. Added.

`ShipyardSwap` is also added to `SUBSCRIBED_EVENTS` for completeness; the
existing stub handler is retained.

---

### Windows — GTK4 Removed

Windows supports **TUI and terminal modes only** from this release. GTK4 is
not available on Windows and is no longer referenced in any Windows-specific
code or documentation.

**`scripts/collect_runtime.ps1`** is rewritten to take `-PythonExe` (standard
CPython from python.org) instead of `-Msys2Root`. It installs `textual`,
`discord-webhook`, `psutil`, and `cryptography` via pip into `dist\runtime\`.
GTK4 DLLs, GI typelibs, GLib schemas, and Adwaita icons are removed from the
bundle entirely. Expected installer size drops from ~300 MB to ~40–60 MB.

**`installer/EDMD.iss`** removes MSYS2 detection, download, and silent install.
The `[Icons]` section has TUI and terminal shortcuts only; the GTK4 GUI shortcut
is removed. `[Code]` retains only Git detection and download logic.

**`.github/workflows/windows-build.yml`** removes the `msys2/setup-msys2@v2`
step entirely. Uses `actions/setup-python@v6` with Python 3.12. Runtime size
threshold lowered from 50 MB to 20 MB.

---

### Files Changed

| File | Change |
|---|---|
| `core/state.py` | VERSION → 20260409; `PATTERN_WEBHOOK` regex fixed (`[A-z0-9_-]` → `[\w-]+`); `state.last_kill_mono` added to `MonitorState`; stale idle alert fields removed |
| `core/plugin_loader.py` | `load_all()` rewritten for flat `components/` scan; subdirectory recursion removed; tier labels updated |
| `core/activity.py` | `_duration_seconds()` added to `ActivityProviderMixin`; `on_summary()` default no-op retained |
| `core/journal.py` | Writes `state.last_kill_mono` on live kills and `LoadGame`; idle alert block removed from live tail |
| `core/data.py` | `normalise_module_name` import path updated to `components.assets.plugin` |
| `components/combat/plugin.py` | `PLUGIN_NAME`, `PLUGIN_DISPLAY`, `PLUGIN_VERSION` added; `SUBSCRIBED_EVENTS` added; emit calls restored; `_duration_seconds` removed (inherited from mixin) |
| `components/missions_session/plugin.py` | New location (was `builtins/activity_missions/`); `PLUGIN_NAME = "missions_session"` |
| `components/alerts/plugin.py` | `"Repair"` and `"ShipyardSwap"` added to `SUBSCRIBED_EVENTS` |
| `components/*/plugin.py` | All: `builtins/` path references updated to `components/`; `activity_` PLUGIN_NAME prefixes removed |
| `tui/app.py` | Update notice bar; `on_key` delegation; `register_tui_app` hook; `check_action` for conditional binding; KSW status in title; `action_toggle_ksw` stub |
| `tui/block_base.py` | `Label(self.BLOCK_TITLE)` — extra spaces removed |
| `tui/blocks/alerts.py` | `VerticalScroll` → `Vertical` |
| `tui/blocks/cargo.py` | Hardcoded `" CARGO "` → `"CARGO"` |
| `tui/blocks/assets.py` | Carrier Hull and Cargo rows added to wallet tab; net worth calculation matches GTK4 |
| `tui/theme.py` | Update notice bar CSS; crew 18%, assets 45%, eng 37% |
| `tui/preferences.py` | `_extra_tabs()` hook for component-injected preference tabs; `collect_tui_prefs` dispatch |
| `edmd.py` | Windows sentinel wait on startup; `components/` on sys.path |
| `edmd_launcher.py` | cmd.exe detection → relaunch in PowerShell; GTK4/MSYS2 runtime fallback retained for legacy installs |
| `installer/EDMD.iss` | MSYS2 removed; TUI + terminal shortcuts only; Git detection retained |
| `scripts/collect_runtime.ps1` | Rewritten for standard CPython; GTK4 DLLs removed |
| `.github/workflows/windows-build.yml` | MSYS2 step removed; standard Python; 20 MB threshold |
| `docs/PLUGIN_DEVELOPMENT.md` | Deleted |
| `docs/guides/WINDOWS_GUI.md` | Deleted |
| `docs/guides/WINDOWS_INSTALLER.md` | Updated for GTK4 removal |
| `docs/CONFIGURATION.md` | `[GUI]` section updated; `WarnNoKillsInitial` removed; `--gui` flag removed |
| `README.md` | GTK4 Windows badge removed; plugin system row removed |
| `INSTALL.md` | GTK4 Windows section updated; dependencies updated |
