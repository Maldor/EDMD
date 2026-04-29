# EDMD 20260308b

> **20260308b** fixes a kill counter regression introduced in 20260308a.
> **20260308a** fixes the kill counter and adds two new features.
> **20260308** is the base release for this date.
> All three are included below.

---

## 20260308b — Kill Counter Cutoff Fix

The kill credit cutoff used to determine "how many kills count toward my remaining missions" was anchored to the wrong event.

**The bug:** When a batch of missions reached quota and fired `MissionRedirected`, the credited kill count was not reset. The bottleneck (total kills required) shrank as those missions were excluded from the calculation, but the credited count stayed high — causing remaining kills to show as 0 when missions still required work.

**The root cause:** The cutoff was set from `MissionCompleted` (reward collection) rather than `MissionRedirected` (quota met). Kills that satisfied redirected missions were being double-counted against the remaining open missions.

**The fix:** The cutoff is now the latest `MissionRedirected` timestamp among currently-active redirected missions for the target faction. Kills before that moment belong to already-completed work. Only kills after the most recent redirect event count toward the remaining open missions.

Both the bootstrap path (startup/relog) and the live path (redirect fires during active monitoring) are fixed.

**Upgrading from 20260308a:** No config changes required. Run `edmd.py --upgrade` or use the Upgrade button in the GUI.

---

## 20260308a — Kill Counter Bottleneck Fix · Kill Display · Not-In-Game Detection

### Kill Counter — Bottleneck Fix

Redirected missions (quota met, awaiting turn-in) were incorrectly included in the bottleneck sum. This inflated the displayed total and produced wrong remaining kill counts mid-stack.

The counter now correctly excludes redirected missions. Only missions with kills still outstanding contribute to the target total.

---

### Kill Display — Remaining Count Only

The `credited / total` format has been replaced with a single remaining count across all output — GUI sidebar, stack-full announcement, periodic summary, and startup status block. The remaining count is the only number that matters and is now the only number shown.

---

### Not-In-Game Detection

EDMD now detects when the player is not in an active session and alerts on Discord or terminal at the highest configured notification level.

Detection is driven by `Music: MainMenu` and `Shutdown` journal events, with a process check as a supporting signal. A **5-minute startup grace** prevents false alerts when EDMD launches before the game client. A **15-minute grace after going to menu** covers brief interruptions. Re-alerts hourly while offline. All periodic output is suppressed until the player returns.

---

## 20260308 — In-Place Upgrade · User Data Directory · Session Persistence · Crew Fix · Avatars · Guides

### In-Place Upgrade — `--upgrade`

```bash
edmd.py --upgrade
```

Verifies git, warns on local changes, pulls latest, re-runs the installer, and replaces the running process via `os.execv`. No subprocess, no new terminal window. When a new version is detected at startup, an **Upgrade** button appears in the GUI sidebar — no terminal required.

---

### User Data Directory

EDMD now uses a platform-appropriate user data directory for `config.toml` and runtime files.

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/EDMD/` |
| Windows | `%APPDATA%\EDMD\` |
| macOS | `~/Library/Application Support/EDMD/` |

Config resolution order: user data directory → repo-adjacent (fallback). `install.sh` creates `config.toml` in the user data directory automatically.

**Existing installs:** move `config.toml` to `~/.local/share/EDMD/config.toml`. The repo-adjacent path remains a permanent fallback.

---

### Session State Persistence

Kill count, credit total, merit total, faction tallies, kill interval data, scan counts, and session start time are now written to `session_state.json` before an upgrade restart and on clean exit. Restored automatically on next launch if the same journal file is active. Stale state from a prior session is never loaded.

---

### Bug Fix — NPC Crew Panel Missing After Relog

The crew block disappeared from the GUI after logging out and back in. Root cause: `CrewAssign` does not reliably re-fire on relog. Fixed in the `Loadout` handler — if a fighter bay is present and `crew_name` is known, `crew_active` is set to `True` immediately on loadout without waiting for `CrewAssign`.

---

### Theme-Matched Avatar Variants

Seven theme-matched avatar variants added to `images/`. The sidebar avatar and Discord webhook resolve the correct variant from the active theme name automatically.

---

### Three New Guides

- **`LINUX_SETUP.md`** — Elite Dangerous on Linux with Steam, Proton, Minimal ED Launcher, EDMC, and EDMD
- **`DUAL_PILOT.md`** — Two accounts on one machine with independent journals, prefixes, and EDMD profiles
- **`REMOTE_ACCESS.md`** — EDMD GUI on a second machine (laptop) as a thin client against your game machine's session

---

## Upgrading

No config changes required for any 20260308 release. Run `edmd.py --upgrade` or use the Upgrade button in the GUI sidebar.

If coming from before 20260308, move `config.toml` to your user data directory (see above) — the repo-adjacent path continues to work as a fallback indefinitely.
