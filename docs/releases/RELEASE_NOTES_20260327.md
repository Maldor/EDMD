# EDMD Release Notes

---

## 20260327

**Elite Dangerous Monitor Daemon — EDMD**

Bug fix and polish release. Resolves long-standing issues with periodic session
summaries not appearing for non-combat sessions, credits not updating live in
the Assets wallet, and the cargo target station reverting to the wrong location
on restart. Redesigns the summary output format. Tightens the update notifier
to release tags only.

---

### Fix — Session Summaries: Root Cause Resolved

Periodic summaries were silently failing across multiple independent failure
modes that accumulated over several sessions of investigation.

**Wrong code path.** The journal monitor routes all events through a
`plugin_dispatch` table in production. The `LoadGame` handler that was meant
to set `state.session_start_time` — the flag the summary trigger checked —
lived in the legacy match block below the early `return` in the dispatch path.
It never executed. All fixes targeting that handler were no-ops.

**Wrong branch.** Even after moving the session anchor to the correct path, the
summary trigger lived inside the `if not line:` sleep branch — the 1-second
idle loop that only runs when the journal has no new content. During active
play, the game writes journal events continuously, so `readline()` always
returns a line and the idle branch never executes. Summaries only fired briefly
on startup before the live event stream began.

**Both fixed.** `state.session_start_time` is now set in the `plugin_dispatch`
block on `LoadGame`. The quarter-hour trigger is moved into the per-event
processing path so it runs on every live event, regardless of how busy the
journal is.

**Firing schedule changed.** Rather than a 15-minute relative timer (which
required tracking monotonic time, reset state, and session anchors), summaries
now fire at wall-clock :00, :15, :30, and :45. Simpler, more predictable, and
no drift.

---

### Fix — Session Summaries: Terminal Suppression

When running in GUI mode, `emit()` suppresses terminal output via a
`not self.gui_mode` guard so the event log panel handles display instead.
Summaries were caught by this guard and silently discarded on the terminal.
`emit_summary` now passes `force_terminal=True`, bypassing the guard
specifically for summaries.

---

### Enhancement — Session Summary Format

The summary output is reformatted for readability in both terminal and Discord.

```
Session Summary
Duration:          2:09:40
  Combat
    Kills:              4  |  1.8 /hr
    Bounties:        1.33M  |  580.6k /hr
  Exploration
    Distance:      7 jumps  |  175 ly
    Bodies scanned:    16  |  2.36M
  Missions
    Completed:          7  |  397.6k credits
```

All values right-justify to a shared column. The `|` delimiter aligns across
every row. Duration is a header row with no indent. Each activity section
appears only when it has data for the current session. Summaries show
cumulative session totals, not per-interval deltas.

Activity rows are also condensed:

- **Exploration:** jumps and distance combined into one row; cartography unsold
  value shown as the bodies-scanned rate field
- **Missions:** completed count and credits in one row
- **Exobiology:** sample count and held/sold value in one row
- **Mining:** tonnes refined with galactic average value estimate as the rate

---

### Fix — Assets Block: Credits Not Updating

`assets_balance` was only refreshed on CAPI polls, which happen on a cooldown.
The Frontier client writes `Status.json` every ~500ms including a live
`Balance` field. The Status.json poller — already running for shields and fuel
— now reads `Balance` and queues a wallet refresh whenever it changes.
Credits now update within half a second of any transaction.

---

### Fix — Assets Block: Ship Value Missing Modules

The Wallet tab's Ships row was summing `HullValue` only from each `Loadout`
event. `ModulesValue` (the fitted loadout cost) was ignored, understating
fleet value by a significant margin. The Loadout handler now stores
`HullValue + ModulesValue`.

---

### Fix — Assets Block: Module Events Not Subscribed

`ModuleRetrieve`, `ModuleStore`, `ModuleBuy`, `ModuleSell`, `ModuleSwap`, and
`ShipyardSwap` were not in the assets plugin's subscription list. The
Ships(N) and Modules(N) tab title counts didn't update until the next
`StoredModules` or `Loadout` event. All six are now subscribed and queue an
immediate assets refresh.

---

### Fix — Cargo Block: Station Reverts on Restart

On startup, the Spansh plugin restored the target station by running a fuzzy
name search against the saved station name string and taking `stations[0]`.
Stations that share a name across systems (e.g. "Rominger City") silently
resolved to whichever result ranked first in Spansh's index — typically not
the intended one.

The saved market ID is now used on startup via the unambiguous
`spansh.co.uk/api/stations/{market_id}` endpoint. The fuzzy search path is
only taken as a fallback when no market ID is saved. The same fix was already
applied to the periodic refresh loop in the previous release — this closes the
`on_load` gap.

---

### Fix — Update Notifier: Post-Release Commits

The update notifier previously ran two checks: (1) compare the latest GitHub
release tag against `VERSION`, and (2) count commits on `origin/main` ahead of
`HEAD`. The commit check fired for any users who had pulled the latest release
but were behind subsequent development commits — normal usage.

The commit check is removed. The notifier now only alerts when a published
release tag is newer than the running `VERSION`. Version comparison handles
lettered patch releases correctly: `20260325a < 20260325b < 20260326`.

---

### Fix — NPC Crew / SLF: Variant Name After Restart

`bootstrap_slf` and `_bootstrap_type_from_journals` were stopping at the first
`RestockVehicle` event found. Frontier omits the `Loadout` field on
`RestockVehicle` when only one variant is stocked — these events resolve to a
bare type name with no variant (e.g. `GU-97` instead of `GU-97 (Gelid G)`).
Both functions now skip events with an empty `Loadout` field and continue
scanning until a specific variant is found.

---

### Fix — Holdings: Voucher Bootstrap on First Run

On first run with no `holdings.json`, the holdings tracker started with all
balances at zero — ignoring bounties, bonds, and trade vouchers earned in
prior sessions. The tracker now scans journal history on first run from the
most recent `Died` event forward, summing voucher events and subtracting
redemptions, to reconstruct the correct unredeemed balance.

---

### Windows Installer: Promoted from Experimental

The `EDMD-Setup-{version}.exe` installer, introduced in 20260323, is promoted
to the recommended Windows installation path. The Experimental caveat is
removed from README, INSTALL.md, and all relevant guides. The manual
MSYS2 and gvsbuild paths in `docs/guides/WINDOWS_GUI.md` remain documented
for users with non-standard setups.
