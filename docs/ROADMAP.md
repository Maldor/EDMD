# EDMD Roadmap

Last updated: 20260429

---

## Active / In Progress

- Review the codebase and find the elements of tech debt that are mentioned
- Review near term goals and see if they are something that still need to be done or if they should be done

---


## Near-term

### Change Versioning
Change the versioning to use semantic versioning rather than date

### Context-aware Commander block
The Commander block shows fixed rows regardless of vehicle. Rows should adapt:

- **On foot:** Fuel → Battery (suit), Shields/Hull → Suit Shield/Health
- **SRV:** Fuel → SRV Fuel, Shields/Hull → SRV Hull
- **Fighter:** Already partially handled (header shows `[In Fighter]`)

Data sources: Status.json Flags bits, Odyssey journal events, `VehicleSwitch`.

---

## Planned Blocks

### Mining Block
Real-time mining session display: prospected asteroids with yield distribution, refined commodities with value estimate, session efficiency.

### ExoBiology Block
Per-body scan progress with species names and estimated values, unanalysed sample indicators, session earnings.

### Combat Zone Block
Active CZ tracking separate from Session Stats: faction, intensity, bonds and rate for the current zone.

### EDDN Powered Wingman Block
Allow you to set up to *n* CMDRs and get events about their state sent to you. Allows Squadron leaders to see status at a glance of their fellows
Would also be useful for Operations to determine if certain actions are needed (Heal, Resupply, Support)

---

## Deferred / Parked

### Profile Switcher GUI
Selector in menu bar, create-new-profile dialog, restart with `-p PROFILENAME`.

### Squadron Carrier Support
Fleet carriers owned by a squadron are not tracked — journal coverage is incomplete.

### Web UI / HTTP Dashboard
Built-in HTTP server with SSE for browser-based remote monitoring. Deferred until GTK GUI reaches stable feature set. See extended design notes in git history.

---

## Known Limitations / Technical Debt

- Stored ship loadouts are only as current as the last time each ship was boarded
- Carrier finance field paths have multiple fallbacks but have not been confirmed across all carrier types — use `--trace` if values are missing
- GTK progressbar warning on close (`GtkGizmo min width -2`) — intentionally set aside
- Block collapse state is not persisted across restarts
- SLF shield state is not tracked — not exposed via journal or Status.json
- Minor faction reputation reflects only the current system; absent between sessions
- On-foot health not shown (requires Status.json field not currently polled)

**Pending docs:** Document CAPI vs. journal tradeoffs for the fleet roster in `docs/CONFIGURATION.md` — what is and isn't available when CAPI is disabled.
