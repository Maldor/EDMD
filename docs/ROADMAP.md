# EDMD Roadmap

Last updated: 20260310b

---

## Active / In Progress

### FDev CAPI Integration
- OAuth2 companion app auth flow
- Primary benefit: `/profile` endpoint gives full fleet regardless of visited shipyard
  — eliminates StoredShips / StoredModules staleness in the Assets block
- Also: live market data, shipyard, outfitting, fleet carrier inventory
- Deferred pending OAuth implementation — non-trivial auth flow

**Note:** Faction reputation and pilot skill ranks do not require CAPI. Reputation
is sourced from the journal `Reputation` event (major factions) and `FSDJump`/
`Location` events (local factions). Ranks are sourced from the journal `Rank`
event. CAPI `/profile` rank data is also consumed where available but is not the
primary source.

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

### CAPI OAuth Flow
- Non-trivial auth flow — defer
- Will inform what additional fields the Assets block can show once available

### Squadron Carrier Support
- Fleet carriers belonging to a squadron (not player-owned) are not currently
  tracked in the Assets block — journal coverage is incomplete

---

## Known Limitations / Technical Debt

- `StoredShips` and `StoredModules` data is stale between shipyard / outfitting visits
  — will be resolved by CAPI `/profile` integration
- Carrier finance and capacity field paths are hardened with multiple fallbacks but
  the exact `/fleetcarrier` JSON structure has not been confirmed in production —
  run with `--trace` after docking at a carrier if values are missing
- GTK progressbar warning on close (`GtkGizmo min width -2`) — set aside intentionally
- Block collapse state is not persisted across restarts — intentional for now
- SLF shield state is not tracked — the game does not expose this via the journal
  or `Status.json`
- Minor faction reputation reflects only the current system and is replaced on each
  jump; it is absent between sessions
