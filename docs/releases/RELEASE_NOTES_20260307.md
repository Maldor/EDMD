# EDMD Release Notes

---

## 20260307.00

**Elite Dangerous Monitor Daemon — EDMD**

---

### Kill Counter — Complete Remodel

The massacre mission kill counter has been rewritten from scratch to match the correct tracking model used by EDMC-Massacre.

**Previous behaviour:** A single global kill count was compared against a single aggregated total, which produced incorrect remaining counts when missions from multiple issuing factions targeted the same faction.

**New behaviour:** Kill tracking is now per target faction. For each target faction `T`, the total required is determined by the bottleneck issuer — the single issuing faction with the highest combined `KillCount` across all its missions targeting `T`. This correctly reflects how the game itself evaluates mission completion.

Display shows one row per target faction (alphabetically sorted), formatted as `remaining / total` (e.g. `192 / 236`). Header reads **Target Faction | Kills Needed**.

**State model changes:**

- New: `mission_killcount_map` — MissionID → KillCount
- New: `mission_target_faction_map` — MissionID → TargetFaction
- New: `mission_issuing_faction_map` — MissionID → IssuingFaction
- New: `target_kill_totals` — TargetFaction → bottleneck total (rebuilt on mission lifecycle events)
- New: `target_kills_credited` — TargetFaction → kills landed since tracking started
- Removed: `kills_required`, `kills_credited`, `faction_kills_remaining`

**Bootstrap fix:** On startup, `bootstrap_kill_counts()` now scans journal history from the earliest active `MissionAccepted` timestamp forward, pre-crediting any `Bounty` or `FactionKillBond` events against the correct target faction. This means the counter correctly shows progress rather than full totals when EDMD is launched mid-grind.

**Mission lifecycle recalc:** `recalc_target_kill_totals()` is called on `MissionAccepted`, `MissionCompleted`, `MissionAbandoned`, and `MissionFailed`. `MissionRedirected` does not trigger recalc — the mission remains live until the reward is collected.

---

### GUI — CSS Theme Architecture Refactor

Themes have been split into a two-file system:

- `themes/base.css` — all structural CSS (layout, spacing, fonts, widget geometry) using `var(--x)` custom properties throughout
- `themes/default*.css` — palette-only files containing a single `:root { }` block of CSS variable definitions (~50 lines each)

**What this means:** Spacing and layout fixes now apply to all themes simultaneously. Creating a custom theme requires only defining colour variables — no knowledge of GTK4 CSS widget selectors needed.

**Spacing tightened** across all themes (~50px total vertical height reduction):

- `right-panel` padding: 10px → 6px
- `panel-section` margin and padding reduced
- `section-header` padding-bottom: 4px → 2px
- `data-row` padding: 2px → 1px

**`load_theme()` updated:** Always loads `base.css` + the selected palette file. Falls back to `default.css` palette if named theme not found.

**New custom theme template:** `themes/custom/my-theme.css` — a heavily commented palette-only template. Documented in README and `example.config.toml`.

---

### GUI — SLF Panel Fixes

Six bugs corrected in SLF and NPC crew panel behaviour:

1. **Crew block hidden on ship switch to non-crew-capable vessel.** Previously persisted incorrectly. Now cleared via `Loadout` handler when no fighter bay is detected.
2. **SLF block visible on non-fighter-capable ships.** Now fully cleared (type, deployed state, loadout, hull) on `Loadout` when no fighter bay is present.
3. **Crew block disappeared on fighter recall (DockFighter).** `crew_active` was incorrectly cleared. Fixed — crew remains visible through the full dock/deploy cycle.
4. **Crew block reappeared on ship switch to non-crew ship.** Fixed by the `Loadout` handler correction above.
5. **Fighter hull not reset to 100% on dock.** Fixed in `DockFighter` handler — SLF is repaired to full integrity on retrieval.
6. **SLF docked state not tracked.** New `slf_docked` flag added to `GameState`. Set on `DockFighter`, cleared on `LaunchFighter` and `FighterDestroyed`. GUI Status row now correctly shows **Docked** / **Deployed** / **Destroyed**.

---

### GUI — SLF Fighter Variant Display

Fighter type display now shows the full model and variant designation, matching the in-game loadout name.

Examples:

- `GU-97 (Gelid F)` / `GU-97 (Rogue F)` / `GU-97 (Aegis F)`
- `F63 Condor (Gelid)` / `F63 Condor (Rogue)` / `F63 Condor (Aegis)`
- `F/A-26 Strike (Gelid F)` / `F/A-26 Strike (Rogue F)` / `F/A-26 Strike (Aegis F)`

Guardian hybrid fighters (Trident, Javelin, Lancer) do not have loadout variants and display type name only.

`FIGHTER_LOADOUT_NAMES` table expanded to include all three variants for all three standard fighter types.

---

### GUI — Kill Counter Target Faction Labels

Long target faction names are now ellipsized at the end (`Pango.EllipsizeMode.END`) rather than wrapping or overflowing. `Pango` is imported from `gi.repository` — it ships with GTK4 and requires no additional package installation.

---

### GUI — Fighter Orders Row Removed

The Orders row has been removed from the SLF panel. Investigation confirmed that `FighterOrders` is not a real journal event, `Status.json` carries no order state, and NPC crew combat chatter (`ReceiveText`) is not reliably present during the order window. There is no accessible data source for this field.

---

### Documentation

- **README — Theming section** rewritten to explain the base/palette split, document `themes/custom/my-theme.css` as the starting point for custom themes, and update the file tree.
- **README — GUI feature list** updated to include NPC Crew panel and correct SLF panel description (type+variant, docked/deployed/destroyed status).
- **`example.config.toml`** — Theme comment updated to reference `custom/my-theme.css` template and explain the palette-only format.
- **INSTALL.md / requirements.txt** — Pango noted as a GTK4 bundled dependency (no install step required).

---

### Known Limitations (unchanged)

- SLF shield state is not tracked — the game does not expose this via journal or `Status.json`
- GTK4 GUI is Linux-only; Windows users have terminal and Discord output
- Theme changes require a restart (no hot-reload for CSS)
