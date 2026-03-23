# EDMD v20260323 — Bug fixes · Activity alerts · Windows installer

## Bug fixes

**Session summary data mismatch.** Periodic summaries sent to Discord and the terminal were showing `Duration: 0:00` and zero rates despite correct data appearing in the GUI. The root cause was two separate session clocks: the GUI used `session_stats._session_start_time` (set on `LoadGame`) while the Discord path used `state.session_start_time` (set by the legacy journal path, unreachable under the new architecture). The summary emitter has been rewritten to use `session_stats.session_duration_seconds()` — the same source as the GUI — and computes all rates from the activity provider data directly. One data path, consistent output everywhere.

**Ships dropping off the assets tab.** When CAPI polled and returned stored ship data, it replaced the full `assets_stored_ships` list rather than merging into it. Ships added or swapped since the last CAPI poll were wiped. CAPI data now merges into the existing journal-derived list — CAPI wins for ships it knows about, journal ships not yet reflected in CAPI are preserved.

**Station lookup defaulting to wrong result.** The Spansh cargo target refreshed on a timer by running a fuzzy name search and taking `stations[0]` — the first of potentially many stations sharing the same name. Selecting "Rominger City" in one system could silently switch to Rominger City in a different system on the next refresh. The market ID is now persisted alongside the station name. Refreshes use `spansh.co.uk/api/stations/{market_id}` — a direct, unambiguous lookup. The user's specific station is preserved across refreshes and restarts.

**NavRoute NameError.** `_read_nav_route_json` was called in the commander component but never defined, producing a terminal warning on every `NavRoute` event. The helper function has been added.

**Fuel duration estimate cross-session contamination.** After a game crash or forced close (no `Shutdown` event), the fuel burn rate timing anchor from the previous session persisted into the new session. The first `ReservoirReplenished` event in the new session was compared against a timestamp hours old, producing estimates in the hundreds of hours. The timing anchors are now cleared on `LoadGame` while the rate itself is preserved as a warm-start estimate. Additionally, `bootstrap_burn_rate()` runs after preload to seed the rate from recent journal history when the current session is too short to calculate it.

**SLF hull damage not reflected in GUI.** The crew/SLF component correctly updated `state.slf_hull` on `HullDamage(Fighter=True)` events but did not put `slf_update` on the GUI queue, so the display never refreshed. Fixed. `fighter_integrity` is also reset on `DockFighter` so the deduplication guard does not suppress valid updates after the fighter re-launches.

## Enhancements

**Session reset button.** A `↺` button has been added to the session stats tab bar. It resets all session counters immediately via `session_stats.on_new_session()`.

**Engineering row hover highlight.** Mousing over a row in the Engineering materials tab now highlights it, improving readability when scanning long lists.

**Fuel kill criteria refinement.** The automatic session-end trigger for low fuel has been reworked into two independent conditions:

- **Fuel % alone** — fires if fuel falls at or below the configured percentage threshold.
- **Duration + fuel % combined** — fires only when *both* estimated time remaining is below the minutes threshold *and* fuel % is below the percentage threshold simultaneously. This prevents false triggers when only one condition is momentarily true.

Both conditions are suppressed entirely while the player is in supercruise, and for a configurable grace period (default 60 seconds, `FuelKillSCGrace`) after exiting supercruise. The state is tracked via `state.in_supercruise` and `state.last_sc_exit_mono` set by the commander component on `SupercruiseEntry` and `SupercruiseExit` events.

**Session-end notifications.** When an automatic session-end trigger fires for any reason, the reason is now emitted to the terminal and Discord at loglevel 3 before the game process is terminated.

## Windows installer (Experimental)

v20260323 introduces a Windows installer: `EDMD-Setup-{version}.exe`, built automatically by GitHub Actions on every release tag.

The installer handles the complete Windows setup in one step:

- Detects or silently installs [MSYS2](https://msys2.org)
- Installs GTK4, Python 3.12, PyGObject, and psutil via `pacman`
- Installs `discord-webhook` and `cryptography` via pip
- Clones the EDMD source from GitHub into `%LOCALAPPDATA%\EDMD\src\` as a live git repository
- Installs `EDMD.exe` — a small launcher that locates MSYS2's Python and GTK4 libraries and executes `edmd.py`
- Creates Start Menu and optional Desktop shortcuts

Because the EDMD source is a real git clone, `EDMD.exe --upgrade` continues to work identically to the Linux upgrade path.

**Requirement:** [Git for Windows](https://git-scm.com/download/win) must be installed and on your PATH before running the installer.

> **This feature is marked experimental.** The installer has not been tested across a wide range of Windows configurations. Terminal mode and GUI mode are both functional. Please report issues via the [issue tracker](https://github.com/drworman/EDMD/issues).

See [docs/guides/WINDOWS_INSTALLER.md](../guides/WINDOWS_INSTALLER.md) for full documentation.
