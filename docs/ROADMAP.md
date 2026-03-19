# EDMD Roadmap

Last updated: 20260319

---

## Active / In Progress

*(Nothing currently blocked — see Near-term for next priorities.)*

---

## Released in 20260318

### Hull integrity real-time tracking fix  ✅ shipped

## Released in 20260319

### Activity plugin architecture  ✅ shipped
Session boundary model, eight activity plugins, tabbed Session Stats, mode plugin removed.
`builtins/alerts/plugin.py` — ready to ship.

Frontier's `HullDamage` journal event fires reliably for SLF hits but
inconsistently for mothership damage. Confirmed across 11 hours of RES
combat: hull dropped from 98% to 88% with zero `HullDamage(PlayerPilot=True)`
events fired. Two fixes implemented:

1. **`Loadout` subscription** — The `Loadout` event fires on dock, undock,
   ship swap, and every SLF dock-back, always carrying accurate `HullHealth`.
   Alerts plugin now updates `state.ship_hull` on every Loadout.

2. **Shield-triggered CAPI poll** — When `ShieldState: False` fires, a
   background thread waits 8 seconds then calls `capi.manual_poll()`. CAPI
   `/profile` returns authoritative hull from Frontier's servers. Rate-limited
   to once per 5 minutes.

Deliverable: `builtin_alerts_plugin.py` in outputs from 2026-03-17 session.

---

## Near-term

### Context-aware Commander block
The Commander block currently shows fixed rows: Mode, Combat Rank, System, Body,
Fuel, Shields/Hull.  These rows should become context-aware and reuse screen
real-estate intelligently depending on what the player is doing.

**Ship mode (current behaviour)**
- Fuel: `XX%  (~Xh Xm)`
- Shields | Hull: `XX%  |  XX%`

**On foot (Odyssey)**
When `VehicleSwitch` To="OnFoot" or equivalent Odyssey boarding events fire:
- Fuel → Battery: `XX%  (~Xm)`  (suit battery from Status.json)
- Shields | Hull → Suit Shield | Health: `XX%  |  XX%`

**SRV mode**
When `VehicleSwitch` To="SRV":
- Fuel → SRV Fuel: `XX%`  (Status.json `Fuel.FuelMain` reflects SRV tank when in SRV)
- Shields | Hull → SRV Hull: `XX%`  (HullDamage events while in SRV)

**Fighter (SLF)**
Already partially handled — header shows `[In Fighter]`.
Row labels do not need to change; SLF has no fuel display.

Implementation notes:
- `pilot_mode` on MonitorState can disambiguate (track "OnFoot" alongside
  "Open", "Solo", "Private Group")
- Status.json `Flags` bits 26-27 give on-foot / SRV state if needed
- Suit health and shield data comes from Status.json and Odyssey journal events
- All changes are purely in `commander_block.refresh()` — no plugin changes needed
  beyond subscribing to the relevant boarding/disembarking events

---

## Planned Blocks

### Mining Block
Track an active mining session in real time. Planned display:
- Prospected asteroids: material yield distribution, % core/fracture flagging
- Refined commodities: per-type count and estimated value at last known market price
- Session efficiency: average yield per asteroid, time per tonne
- Source: `ProspectedAsteroid`, `MiningRefined`, and `AsteroidCracked` journal events

### ExoBiology Block
Track organic scan progress across bodies in the current system and session.
Planned display:
- Species found/analysed per body, with genus/species name and estimated value
- Unanalysed samples (first/second/third scan indicators)
- Session earnings from `SellOrganicData`
- Source: `ScanOrganic`, `SellOrganicData`, `SAAScanComplete`

### Combat Zone Block
Real-time CZ session tracking separate from the main Session Stats block.
Planned display:
- Active conflict zone (system, faction, intensity)
- Combat bond earnings, bond rate, and kill count for the current CZ
- War/civil war progress indicators where available from journal
- Source: `FactionKillBond`, `ReceiveText` (faction intel), `Location`

### Colonisation Block
Track colony construction contributions and progress.
Planned display:
- Active construction site (system, body, type)
- Resources delivered vs. required, per commodity
- Progress toward completion
- Source: `ColonisationContribution`, `ColonisationSystemClaimed`, `Location`
- Note: FDev event coverage for colonisation is still evolving — this block
  will be implemented once the journal schema stabilises

---

## Deferred / Parked

### Profile Switcher GUI
- Selector in menu bar or title bar
- Create-new-profile dialog writing a fully-defaulted `[PROFILENAME]` section to config.toml
- Restart with `-p PROFILENAME`

### Squadron Carrier Support
- Fleet carriers belonging to a squadron (not player-owned) are not currently
  tracked in the Assets block — journal coverage is incomplete

---

## Known Limitations / Technical Debt

- Stored ship loadouts (modules, engineering) are sourced from journal `Loadout`
  events accumulated across sessions — the most recent fitting for each confirmed
  owned ship is persisted in `~/.local/share/EDMD/plugins/assets/data.json`.
  This data is only as current as the last time each ship was boarded.
- Carrier finance and capacity field paths are hardened with multiple fallbacks but
  the exact `/fleetcarrier` JSON structure has not been confirmed in production —
  run with `--trace` after docking at a carrier if values are missing
- GTK progressbar warning on close (`GtkGizmo min width -2`) — set aside intentionally
- Block collapse state is not persisted across restarts — intentional for now
- SLF shield state is not tracked — the game does not expose this via the journal
  or `Status.json`
- Minor faction reputation reflects only the current system and is replaced on each
  jump; it is absent between sessions

**TODO (next release docs):** Document the CAPI tradeoff in the main user
documentation (not just release notes). Specifically:
  - When CAPI is enabled: fleet roster is authoritative (Frontier server),
    sold ships are automatically excluded, hull % and rebuy costs are available.
  - When CAPI is disabled: roster is sourced from the most recent `StoredShips`
    journal event (correct at last dock; cannot detect sales between sessions),
    hull % and rebuy costs are unavailable for stored ships, and phantom ships
    from recent sales may appear until the next dock. Loadout data is unaffected
    — it comes from journal `Loadout` events regardless of CAPI status.
  Suggested location: `docs/CONFIGURATION.md` under a new "CAPI Integration"
  section, and a brief note in `README.md` features table.

---

## Consideration — Web UI / HTTP Dashboard

*Filed for review. Do not implement without explicit confirmation.*

### Background
EDMD currently supports a thin-client / remote profile mode (Configuration B):
the daemon runs on a second machine reading journals over SSHFS, GTK4 GUI is
forwarded via SSH X-forwarding. This works but has friction — X-forwarding has
latency and requires a desktop session on the remote end.

The question: would a built-in HTTP server serving a browser-based dashboard be
a better remote interface?

### What would actually be built

A built-in HTTP server (Flask or stdlib `http.server`) exposing:
- A single-page HTML/JS/CSS dashboard served on a configurable port
- Server-Sent Events (SSE) stream pushing state updates to the browser
  (same events that currently drive `gui_queue` would also push JSON to clients)
- HTTP POST endpoints for interactions (tab switches, target market search,
  alerts clear, etc.)

Web blocks would be HTML/CSS/JS equivalents of the GTK blocks — new code,
not a port of the existing GTK implementation.

### Tradeoffs

**For:**
- Works from any device with a browser — phone, tablet, another PC, no X-forwarding
- No GTK dependency on the viewing device
- Genuinely useful for the "check on your session from another room" use case
- Read-only view would be ~20% of the effort for ~80% of the value
- CSS theming is conceptually portable (different renderer, but shared design intent)

**Against:**
- Maintenance burden: every block needs a GTK version AND a web version, forever
- New blocks take roughly double the development effort
- Full interactive parity (drag/resize/collapse blocks, search fields) is substantial work
- Security surface: HTTP server on the LAN needs at minimum config-driven bind address
  and optional token auth — not complex but must be done properly
- SSE is simpler than WebSockets but still needs careful connection lifecycle management

### Recommended approach if pursued

**Phase 1 — Read-only monitoring view** (lower effort, high value)
A "wall display" layout: Commander status, hull/shields, session stats, cargo,
mission stack, alerts — all live-updating. No interactive elements. Serves the
primary remote use case.

**Phase 2 — Surgical interactivity** (as needed)
Add specific interactive endpoints only where genuinely needed for remote use:
trigger end session, clear alerts, set cargo target market.

**Phase 3 — Full parity** (significant ongoing investment, decide later)
Full block interaction, theme switching, layout persistence via browser storage.

### Config sketch (if implemented)
```toml
[WebUI]
Enabled   = false         # disabled by default
Port      = 8642
BindAddr  = "127.0.0.1"  # "0.0.0.0" for LAN access
Token     = ""            # optional Bearer token for basic auth
```

### Decision pending
Deferred. Revisit once the GTK GUI reaches a stable feature set and the
maintenance cost of dual-frontend development is better understood.
---

## TODO / Pending Consideration

### Session Stats — value-only row alignment
Rows without a rate separator currently right-align their value across
cols 1–3 of the stats grid (the full value+pipe+rate span). This means
a value-only row's text sits further right than the value portion of a
value+rate row, which is mildly inconsistent.

Alternative: value-only rows right-align to col 1 only (the value column),
leaving cols 2–3 empty. Values would then align with the value portion of
rate rows rather than the rate portion.

Decision deferred — review visually in practice before changing.
