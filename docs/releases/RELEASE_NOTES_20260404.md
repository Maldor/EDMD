# EDMD Release Notes

---

## 20260404

**Elite Dangerous Monitor Daemon — EDMD**

Bug fix, polish, and infrastructure release. Resolves mission stack redirect
overcounting, idle session false-positive alerts, and several GUI entry-field
regressions. Rewrites the Windows installer to ship a fully bundled Python and
GTK4 runtime — eliminating MSYS2 as a user-side dependency. Drops Flatpak,
macOS, upgrade-command, and legacy profile-migration code. Adds a Home
Location feature to the Commander block, corrects Discord summary formatting,
and completes a full audit of the example config against actual defaults.

---

### Fix — Mission Stack: Redirect Count Overcounting

The mission stack block reported an inflated redirected-mission count across
restarts. Root cause: two preload guards working against each other.

`MissionCompleted` carried a `not state.in_preload` guard, so turn-in events
were skipped during preload. When EDMD restarted after a session where all
missions had been redirected, the persisted `_redirected` set retained all
prior-session mission IDs. The `Missions` bulk-event handler — which would
normally prune `_redirected` to the intersection of currently-active missions
— was itself skipped when `state.missions` was already `True` from the prior
preload. `MissionRedirected` had no preload guard on the accumulation path, so
new redirects were added to the stale set.

The result: old completed missions inflated the count, and any new redirects
were added on top.

**Fix 1 — `MissionCompleted` preload guard removed.** Turn-in events now
drain `_redirected` during preload exactly as they do live. The Discord/
terminal notification emits remain inside an `if not state.in_preload:` guard.

**Fix 2 — Safety-net pruning in `_restore()`.** On every startup,
`_redirected &= set(state.active_missions)` runs immediately after loading
from storage, discarding any persisted IDs that are no longer in the active
mission list before any journal events are processed.

Both fixes are independently correct; together they are belt-and-suspenders.
Verified against real journal data: 13 active, 3 redirected — confirmed
correct.

Also affects Discord and terminal mission update notifications which read
`state.missions_complete`, and the summary line in `get_summary_line()`.

---

### Fix — Idle Session Alert: False Positive on Active Sessions

Two bugs combined to produce "No kills in N hours" alerts during active combat
sessions.

**Bug 1 — `last_kill_mono` zeroed mid-session.** `FSDJump` triggered
`state.sessionend()`, setting `session_start_time = None`. The next scan or
kill called `state.sessionstart(active_session)`, which saw
`session_start_time is None` and called `active_session.reset()`, zeroing
`last_kill_mono` even for sessions with kills in progress. The idle checker's
fallback then measured time since `last_periodic_summary` — not since the
actual last kill.

**Bug 2 — `last_periodic_summary` never updated after firing.** The fallback
timer reference `last_periodic_summary` was set once at `LoadGame` and never
updated when the quarter-hour summary actually fired, so for long sessions it
drifted hours into the past. Combined with the zeroed `last_kill_mono`, the
idle checker reported the full session duration as dead time.

**Fix 1 — `sessionstart()` preserves kill history mid-session.** The
`active_session.reset()` call is now guarded by
`if reset or not active_session.last_kill_mono:`. Forced resets
(manual, warzone drop) and true new sessions still reset fully. Mid-session
`sessionstart()` calls from cargo scans after a jump no longer wipe the kill
counter. Alert cooldowns are always cleared so per-zone alerting still works.

**Fix 2 — `last_periodic_summary` updated on every summary fire.** One line
added immediately after `emit_summary()` in the quarter-hour block:
`state.last_periodic_summary = time.monotonic()`. The fallback timer is now
at most 15 minutes stale, not hours.

---

### Fix — EDDN: Startup `FSSSignalDiscovered` Mismatch Warning

On every startup, EDMD printed:

```
[EDDN] FSSSignalDiscovered flush: first signal SystemAddress mismatch — dropping batch
```

During preload, historical `FSSSignalDiscovered` events accumulated from
whatever system the player was in during the prior session. The first
non-FSS event triggered a flush, which compared those stale signals against
the current system address and found a mismatch — a guaranteed failure for
any system change between sessions.

The fix: during preload, `self._fss_signals` is cleared silently instead of
flushing. Historical data should never be re-transmitted to EDDN, and the
mismatch warning was a symptom of attempting to do so.

---

### Feature — Commander Block: Home Location

A persistent home location can now be set from the Commander block's Info tab.

A footer search field (placeholder "Set Home Location…") searches Spansh for
both systems (⭐) and stations/outposts (🚉). Results appear in a popover
anchored to the entry. On selection the entry returns to its placeholder so
the field is clearly available for a new search; the clear button (✕) remains
active while a home is set.

The **Home** row in the Info tab (between System and Body) displays:
`SYSTEM` or `STATION (SYSTEM)  |  N,NNN ly away`

Distance is computed live as the Euclidean distance between the commander's
current galactic coordinates and the stored home coordinates, updated on every
`FSDJump` and `Location` event via a new `pilot_star_pos: list | None` field
on `MonitorState`. The Spansh `search_home()` method returns star coordinates
where the API provides them.

Home location is persisted to `data.json` in the commander plugin's storage
directory and restored on startup. If no home is set the row shows `unknown`.

The Commander block footer matches the Cargo block's look and feel exactly:
same compact button CSS, same GLib idle-callback build pattern, same
`set_valign(CENTER)` and `set_width_chars(16)` on the entry.

New in `core/components/commander/plugin.py`:
`_load_home_location()`, `get_home_location()`, `set_home_location()`,
`clear_home_location()`, `home_distance_ly()`.

New in `core/components/spansh/plugin.py`: `search_home(query)`.

---

### Fix — GUI: Footer Entry Vertical Growth

Both the Cargo block target-market entry and the Commander block home
search entry expanded vertically when text was entered and did not return
to their original height. The growth was caused by `set_icon_from_icon_name()`
— GTK4 permanently allocates icon-slot padding into the entry's height the
first time an icon is set, and does not reclaim that height even after the
icon is removed.

All `set_icon_from_icon_name` calls have been removed from both entries.
The popover's appearance and the clear-button's sensitivity provide
sufficient interaction feedback without icons. `set_valign(Gtk.Align.CENTER)`
is applied to both entries to prevent vertical stretching within the footer
box.

---

### Enhancement — Cargo Block: Entry Cleared After Selection

After selecting a target station from the Cargo block popover, the search
entry now returns to its placeholder text ("Target market…") instead of
retaining the station name. The clear button (✕) remains active, signalling
that a target is set and can be cleared. This matches the Commander block's
home search behaviour.

The `refresh()` sync block that previously repopulated the entry with the
station name on every data refresh has been removed; the clear button's
sensitivity is maintained without overwriting the entry.

---

### Enhancement — Discord Summary: Fuel Line Alignment and Collapse

Two formatting fixes to the quarter-hour summary sent to Discord.

**Collapse.** Single-row sections where the label matches the section title
(currently only Fuel) are collapsed to a single line at section-header indent,
eliminating the redundant header row:

```
Before:                        After:
  Fuel                           Fuel:            89%  |  ~19h 23m
    Fuel:        89%  |  ~19h
```

**Alignment.** The collapsed row now pads the label field by +2 to
compensate for the 2-space section indent vs the 4-space data indent,
keeping the value column and `|` delimiter aligned with all other data rows.

---

### Enhancement — Update Notifier: Correct Redirect URL

The version update notice in the titlebar previously directed users to
`File → Upgrade`, which was removed in the preceding release. The notice
now shows `github.com/drworman/EDMD/releases/latest` directly.

---

### Enhancement — Mission Stack Block: Session Kill Suffix Removed

The `(+N this session)` suffix appended to each faction's kill count in the
Mission Stack block has been removed. It caused the block to expand
horizontally, breaking the grid layout.

---

### Removal — Upgrade Command and Menu Item

`--upgrade` and `--upgrade-nightly` CLI arguments are removed from `edmd.py`.
The `_do_upgrade()` function and all upgrade menu items are removed from
`gui/menu.py`. EDMD no longer attempts to self-update; users download new
releases from `github.com/drworman/EDMD/releases/latest`.

---

### Removal — Legacy Profile Format Migration

The config format migrator (`_needs_migration`, `_migrate_text`,
`migrate_config_format`, and their supporting constants and regexes) is removed
from `core/config.py`. `load_config_file` no longer calls the migrator. All
users have been on the dotted-key profile format (`[EDP1]` with
`Settings.JournalFolder = ...`) long enough that the migration path is dead
code.

`migrate_legacy_cmdr_files()` and its import are likewise removed from
`core/state.py` and `edmd.py`. The one-time flat→per-commander file migration
has run on every affected install.

---

### Removal — Flatpak and macOS Support

Flatpak distribution and macOS support are removed. The Flatpak PR to the
Flathub repository remains open but the in-tree infrastructure is removed.
macOS is removed from `_user_data_dir()`, `INSTALL.md`, and all related
documentation. `install_macos.sh` and `docs/guides/MACOS_SETUP.md` are deleted.

---

### Windows Installer: Bundled Runtime (No MSYS2 Required)

The Windows installer is substantially rewritten. MSYS2 is now used
**at build time only** — users no longer need it installed.

A new `scripts/collect_runtime.ps1` PowerShell script runs in CI after MSYS2
installs the full GTK4 + Python stack. It collects into `dist/runtime/`:

- `python.exe` (MSYS2 UCRT64)
- 155 GTK4 and Python DLLs from `ucrt64/bin/`
- Full Python stdlib and site-packages (including gi, psutil, discord-webhook,
  cryptography via pacman)
- 72 GI typelibs
- Compiled GLib schemas
- Adwaita icon theme

`discord-webhook` is installed via pip into the MSYS2 Python before the lib
copy. `cryptography` is installed via pacman (`mingw-w64-ucrt-x86_64-python-
cryptography`) to avoid the MinGW wheel-tag incompatibility that prevents pip
from finding a binary wheel.

A `python3XX._pth` file is written into the runtime root to redirect Python's
library search path to the bundled stdlib.

The Inno Setup script ships `dist\runtime\*` → `{app}\runtime\` alongside
`EDMD.exe`. The launcher's priority order is now:

1. `{app}\runtime\python.exe` (bundled — always used on fresh installs)
2. MSYS2 UCRT64 (fallback for manual / pre-bundle installs)

A CI validation step (`windows-build.yml`) verifies that `dist\runtime\`
is larger than 50 MB and that `installer\EDMD.iss` references the runtime
before invoking Inno Setup, catching stale ISS files early.

Installer output: **~66 MB** (lzma2/ultra64 compressed).

---

### Configuration: Example File Completed

`example.config.toml` is now a complete reference for every supported key.

Previously missing entries added:

- `[Settings]` — `WarnNoKillsInitial` (5), `TruncateNames` (30)
- `[LogLevels]` — `PeriodicKills`, `PeriodicFaction`, `PeriodicCredits`,
  `PeriodicMerits` (the quarter-hour summary notify levels)
- `[REMOTE.LogLevels]` — same four periodic keys
- `[Inara]` — section was entirely absent

Corrected defaults:

- `Discord.Timestamp` was `false`, default is `true`
- `LogLevels.PoliceScan` was `0`, default is `2`

---

### Default Layout Updated

`example.layout.json` is updated to the new internal default layout. The
previous `layout.json.example` filename is renamed to `example.layout.json`
for consistency with `example.config.toml`.

---

### Files Changed

| File | Change |
|------|--------|
| `core/state.py` | `sessionstart()` preserves `last_kill_mono` mid-session; safety-net pruning removed from `_restore()`; `migrate_legacy_cmdr_files()` removed; macOS removed from `_user_data_dir()`; `pilot_star_pos` added to `MonitorState`; VERSION → 20260404 |
| `core/journal.py` | `last_periodic_summary` updated after every `emit_summary()` fire; EDDN FSS flush silenced during preload |
| `core/config.py` | 182 lines of migration code removed; `load_config_file` no longer calls migrator |
| `core/emit.py` | Single-row sections collapse to one line at section-header indent; label padding corrected to keep value column aligned |
| `core/components/missions/plugin.py` | `MissionCompleted` preload guard removed; emit/GUI calls remain guarded; `_restore()` safety-net pruning added |
| `core/components/commander/plugin.py` | `_load_home_location()`, `get_home_location()`, `set_home_location()`, `clear_home_location()`, `home_distance_ly()` added; `StarPos` captured from `FSDJump` and `Location` events into `state.pilot_star_pos`; `home_location.json` → `data.json` |
| `core/components/spansh/plugin.py` | `search_home()` added — returns systems and stations with `is_station`, `star_pos`, `system` fields |
| `gui/app.py` | Update notice now shows releases URL instead of `File → Upgrade` |
| `gui/menu.py` | All upgrade menu items removed; `install_context` import removed |
| `gui/blocks/commander.py` | `Home` row added to Info tab; footer home search UI (entry + clear button); `pilot_star_pos` tracked; all `set_icon_from_icon_name` calls removed; focus surrendered via `root.set_focus(None)` after selection; `cmdr-footer-btn` CSS class |
| `gui/blocks/cargo.py` | Entry cleared after result picked; all `set_icon_from_icon_name` calls removed; refresh sync no longer repopulates entry; `set_valign(CENTER)` added |
| `gui/blocks/missions.py` | `(+N this session)` suffix removed from kill count display; `any_session_kills` and `sess_k` render-loop variables removed |
| `themes/base.css` | `.cmdr-footer-btn` rule added |
| `builtins/eddn/plugin.py` | `FSSSignalDiscovered` batch silently discarded during preload instead of flushing |
| `edmd.py` | `--upgrade`/`--upgrade-nightly` args removed; `_do_upgrade()` removed; `migrate_legacy_cmdr_files` import and call removed |
| `installer/EDMD.iss` | `dist\runtime\*` source line added; old MSYS2 bash-script generation removed |
| `scripts/collect_runtime.ps1` | New — collects GTK4 + Python bundled runtime from MSYS2 at build time |
| `.github/workflows/windows-build.yml` | MSYS2 pacman packages updated; runtime validation step added; `collect_runtime.ps1` invocation |
| `example.config.toml` | `WarnNoKillsInitial`, `TruncateNames`, four `Periodic*` log levels, `[Inara]` section added; `Timestamp` and `PoliceScan` defaults corrected |
| `example.layout.json` | New internal default layout (renamed from `layout.json.example`) |
| `INSTALL.md` | macOS section removed |
| `install_macos.sh` | Deleted |
| `docs/guides/MACOS_SETUP.md` | Deleted |
| `core/install_context.py` | Deleted |
