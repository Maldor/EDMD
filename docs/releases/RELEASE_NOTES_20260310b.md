# EDMD Release Notes

---

## 20260310b

**Elite Dangerous Monitor Daemon — EDMD**

Patch release. Fixes CAPI rank display, corrects Federation and Empire rank
tables, moves faction reputation to a Journal-sourced implementation, standardises
scrollbars across all dashboard blocks, fixes carrier finance display, adds alerts
auto-clear on login and docking, extends the update notifier to detect unpulled
git commits, and moves CAPI verbose output behind the `--trace` flag.

---

### Bug Fix — CAPI Rank Keys Lowercase

CAPI `/profile` returns all rank keys lowercase (`combat`, `trade`, `explore`,
`cqc`, `soldier`, `exobiologist`, `empire`, `federation`). `CAPI_RANK_SKILLS`
in `core/state.py` was using titlecase keys, causing all CAPI-sourced rank
lookups to silently miss and display blank or stale values.

All keys in `CAPI_RANK_SKILLS` are now lowercase, matching the actual API
response. No application-level normalisation is required.

---

### Bug Fix — Federation and Empire Rank Tables Corrected

`RANK_NAMES_FEDERATION` was a verbatim copy of the feudal Empire titles due to a
copy-paste error. Both tables are now correct.

**Federation** (ranks 0–14): None → Recruit → Cadet → Midshipman → Petty Officer
→ Chief Petty Officer → Warrant Officer → Ensign → Lieutenant → Lieutenant
Commander → Post Commander → Post Captain → Rear Admiral → Vice Admiral → Admiral

**Empire** (ranks 0–14): None → Outsider → Serf → Master → Squire → Knight →
Lord → Baron → Viscount → Count → Earl → Marquis → Duke → Prince → King

Federation and Empire ranks were already present in the CAPI rank dict (`empire: 7`,
`federation: 7`) but had no table to resolve names from. Both are now entries in
`CAPI_RANK_SKILLS` and display correctly in the Commander block Ranks tab.

---

### Feature — Faction Reputation: Journal-Sourced with Major / Minor Split

Faction reputation does not appear in the CAPI `/profile` response. The Rep tab
previously attempted to read it from CAPI and always showed blank.

Reputation is now sourced entirely from the journal:

**Major factions** come from the journal `Reputation` event, which fires on login
and after standing changes. It provides floating-point standings (0–100) for
Federation, Empire, Alliance, and Independent. These are stored in
`state.pilot_reputation` and persist for the session.

**Minor / local factions** are harvested from the `Factions[].MyReputation` array
in `FSDJump` and `Location` events. These are stored in
`state.pilot_minor_reputation` as a dict keyed by faction name, replaced on each
jump or location update to reflect the current system's factions.

The Commander block Rep tab now shows two sections: **MAJOR FACTIONS** (always
present after first login event) and **LOCAL FACTIONS** (current system only,
replaced on jump). Minor faction rows are built dynamically and sorted by standing
descending.

---

### Fix — GTK4: `set_line_wrap` → `set_wrap`

`set_line_wrap()` is a GTK3 method. GTK4 uses `set_wrap()`. The call in the
commander block Rep tab was silently failing on GTK4, causing label text to
overflow without wrapping. Fixed.

---

### Feature — Scrollbar Standardisation Across All Blocks

`BlockWidget._make_scroll_body(parent)` is now a standard helper in
`gui/block_base.py`. It returns a vexpand `ScrolledWindow` with:

- `NEVER / AUTOMATIC` scroll policy
- `mat-tab-scroll` CSS class
- `margin_end(12)` on the inner box to keep content clear of the GTK4 overlay
  scrollbar track

The following blocks were updated to use this helper or were otherwise missing
the correct scroll treatment:

- **Cargo** — was missing `mat-tab-scroll` CSS class and `margin_end(12)`
- **Missions** — had no scrollable body at all
- **Session Stats** — had no scrollable body at all
- **Alerts** — had no scrollable body; Clear button is now pinned below the
  scroll region with `margin_end(12)`
- **Crew / SLF** — had no scrollable body at all
- **Commander** Ranks / Rep tabs — had `ScrolledWindow` but missing `margin_end(12)`

Plugin authors writing custom blocks should use `self._make_scroll_body(parent)`
rather than constructing `ScrolledWindow` manually. See the updated Plugin
Development guide.

---

### Bug Fix — Carrier Finance and Capacity Not Displaying

The Assets block Carrier tab showed `—` for credit balance, reserved credits,
cargo capacity, and free space after a CAPI poll.

Root cause: the `/fleetcarrier` JSON response nests finance and capacity fields
under different keys than expected, and returns numeric values as strings rather
than integers in some cases.

Fix: field path resolution now tries multiple fallback keys in order for both
the `finance` and `capacity` containers. All numeric values are now cast through
an `_int()` helper that handles both string and integer inputs before any
arithmetic. The CAPI plugin now also dumps the raw top-level keys, finance
object, and capacity object under `--trace` to assist diagnosis if field paths
change again in a future CAPI version.

---

### Feature — Alerts Auto-Clear on Login and Docking

The Alerts block now clears automatically on `LoadGame` and `Docked` events.
Alerts present from a previous session or from pre-dock activity are stale by
the time the player loads into a new ship or docks, and clearing them
automatically avoids the player needing to dismiss them manually.

Clears are silent (no announcement) and only fire during live play, not during
journal preload replay.

---

### Feature — Update Notifier: Unpulled Commit Detection

The update check now covers two cases:

1. **New release** — GitHub releases API, as before. Shows a release badge in
   the header bar with the new version number.

2. **Unpulled commits** — if no new release is found, and `git` is on `PATH`,
   and EDMD is running from inside a git work tree, the notifier runs
   `git fetch origin main` followed by `git rev-list --count HEAD..origin/main`.
   If commits are available that are not yet pulled, the badge shows the count
   instead of a version string.

**File → Upgrade** handles both cases identically using the existing `git pull`
path. The commit check is fully silent if `git` is not found or EDMD is not
running from a git repository.

---

### Feature — CAPI Verbose Output Behind `--trace`

All `[CAPI]` diagnostic print statements in `builtins/capi/plugin.py` are now
gated on `core.trace_mode`. They are completely silent by default and only
appear when EDMD is launched with the `--trace` (`-d`) flag. This eliminates
noise in normal terminal output while preserving full visibility for debugging.

---

### Upgrading

No config changes required when upgrading from 20260310a.

`layout.json` does not need to be deleted. The grid engine will backfill any
missing block entries automatically.

The Rep tab will show "Awaiting login data…" on first launch until a `Reputation`
journal event is replayed. This populates immediately on the next game login.

---

### Known Limitations

- Carrier finance and capacity field paths are hardened with multiple fallbacks
  but the exact `/fleetcarrier` JSON structure has not been confirmed in
  production. Run with `--trace` after docking at a carrier to see raw field
  names if values are still missing
- `StoredShips` and `StoredModules` data is stale between shipyard / outfitting
  visits — will be resolved by CAPI `/profile` integration
- GTK4 GUI is Linux-native; Windows and macOS are best-effort
- SLF shield state is not tracked — the game does not expose this via the
  journal or `Status.json`
- Block collapse state is not persisted across restarts — intentional for now
- Minor faction reputation reflects only the current system; it is replaced on
  each jump and is absent between sessions
