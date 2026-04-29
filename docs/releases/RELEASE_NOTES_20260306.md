# EDMD Release Notes

---

## 20260306 — Initial Release

**Elite Dangerous Monitor Daemon — EDMD**

This is the first public release of EDMD. It consolidates all development work into a clean, stable build under a new name and date-based versioning scheme. Versions follow the format `YYYYMMDD` with an optional `.xx` patch suffix for same-day updates.

---

### Core Monitoring

Real-time journal tail with automatic detection of new journal files between game sessions. Preloads the current journal at startup to establish initial state before live monitoring begins.

**Kill & reward tracking:** Logs every `Bounty` and `FactionKillBond` event with ship type, faction, credit value, and time since last kill. Kill rate and inactivity warnings with configurable thresholds and exponential backoff.

**Periodic summaries:** Delivered every 10 kills and on session exit — to terminal, GUI, and Discord. Includes duration, kill count and rate, credit total and rate, mission stack value, and merit total and rate.

**Fuel monitoring:** Tracks fuel level on every tick, with separate warn and critical thresholds. Estimated time-remaining calculated from recent consumption rate.

**Damage & combat alerts:** Shield raise/drop events, fighter hull damage at 20% intervals, ship hull damage events, SLF launch/dock/orders.

**Security & cargo:** Inbound scan detection, police scan and attack alerts, low-cargo-value pirate alerts.

---

### Massacre Mission Stack

Full mission lifecycle tracking with journal bootstrap from complete history. Reconstructs active mission list, reward values, and kill progress accurately regardless of when EDMD is launched relative to the game session. Filters expired missions by `Expiry` timestamp.

---

### GTK4 GUI (Linux)

Full graphical interface with live-updating panels:

- Event log (scrolling, left panel)
- Commander: name, ship, mode, rank, powerplay allegiance, progress bar
- NPC Crew: name, rank, hire date, active duration, total earnings
- Ship-Launched Fighter: type and variant (e.g. GU-97 Gelid F), docked/deployed/destroyed status, hull integrity, active orders
- Mission Stack: value, completion progress
- Session Stats: kills, credits, merits with per-hour rates and session duration
- PowerPlay progress bar (when applicable)
- Sponsor / links panel

Eight built-in CSS themes. Custom theme support via `themes/custom/` (gitignored). Hot-reload not yet applied to theme — restart required for theme changes.

---

### Discord Integration

Structured webhook notifications with per-event log levels (0=off, 1=terminal, 2=+Discord, 3=+ping). Rich startup embed. Forum channel and thread support. Duplicate suppression with configurable cap before flood protection engages.

---

### Config System

TOML-based configuration with hot-reload for most settings (~1 second on save). Named profiles for per-commander or per-account overrides. Profile auto-selection by commander name. Full HOT/RESTART annotations in example config.

---

### Session Management

Authorized users can configure EDMD to exit the game process automatically on configurable trigger conditions (low fuel by percentage or estimated time remaining, fighter destroyed, low ship hull). Configured per-profile. Targets `EliteDangerous64.exe` with graceful SIGTERM followed by force-kill after 5 seconds.

SLF destruction during supercruise entry (forced fighter recall) does not trigger session exit — this is intentional behaviour to avoid false positives when jumping with a deployed fighter.

---

### NPC Crew

Crew presence bootstrapped from full journal history. Tracks name, rank, hire date, active duration, and total wages paid. Block hidden on ships without fighter bay support.

---

### Versioning

Prior to this release the project used a `XX.XX.XX` version scheme. Versions are now date-based: `YYYYMMDD` for daily releases, `YYYYMMDD.xx` for same-day patches. GitHub release tags follow the same format and are used for update notifications.

---

### Known Limitations

- SLF shield state is not tracked (game does not expose this in journal or Status.json)
- GTK4 GUI is Linux-only; Windows users have terminal and Discord output
- Theme changes require a restart (no hot-reload for CSS)
