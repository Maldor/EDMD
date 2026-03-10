# EDMD Release Notes

---

## 20260310a

**Elite Dangerous Monitor Daemon — EDMD**

Combined feature and patch release. This note covers all changes shipped in
20260310 and 20260310a. Upgrading from any 20260309x release brings in
everything listed here.

---

### Feature — Assets Dashboard Block

A new fleet overview block. Tracks and displays the full commander asset picture
in a single panel with three tabbed sections:

**Ships** — current ship (name, type, hull %, location) plus all stored ships,
resolved from journal history. The current ship is always listed first with a
★ indicator. Ships are de-duplicated by ShipID so the same hull never appears
twice regardless of how journal events are ordered.

**Modules** — stored module inventory with slot classification, system location,
hot-goods flagging, mass, and estimated value.

**Carrier** — fleet carrier callsign, name, current system, tritium fuel level
(bar + numeric), credit balance, cargo capacity, and docking access state.

Name resolution for ship types works in three layers: `ShipType_Localised` from
the journal event, a cache built from Shipyard events encountered across the
player's journals, and a static fallback map covering all ship types.

---

### Feature — Engineering / Materials Dashboard Block

A new block for engineering materials inventory. Displays Raw, Manufactured, and
Encoded categories in a single scrollable panel. Item counts update live as
materials are collected, traded, or used at engineers.

Replaces the earlier Materials block prototype from 20260309b/c, which is removed.

---

### Feature — Inara Integration

Opt-in integration with [Inara.cz](https://inara.cz). Posts flight log entries
and combat events and can pull CMDR profile data to supplement local state.
Configured under `Preferences → Data & Integrations`. Uses the same opt-in
architecture as the EDDN, EDSM, and EDAstro plugins.

---

### Feature — Fuel Display in Commander Block

The Commander block now shows live fuel level with an estimated time remaining
based on the current burn rate. Two configurable thresholds (warn / critical)
control when the value changes colour. Both thresholds default to 20% and 10%
and are adjustable in `config.toml` under `[Commander]`.

---

### Feature — Windows and macOS GUI Support (best-effort)

The GTK4 GUI is no longer documented as Linux-only. Two paths for Windows and
one path for macOS are provided, each with a dedicated installer and guide.

**macOS** — GTK4 and PyGObject via Homebrew. Expected to work on macOS 13
Ventura or newer with no code changes.

```bash
bash install_macos.sh
```

**Windows — Option A (MSYS2, recommended)** — GTK4 and PyGObject via MSYS2
`pacman`, running inside the MSYS2 UCRT64 terminal.

```bash
bash install_msys2.sh
```

**Windows — Option B (gvsbuild, advanced)** — Native GTK4 build using Visual
Studio Build Tools. Runs from CMD or PowerShell with no MSYS2 dependency.

```bat
install_gvsbuild.bat
```

Developer notice: EDMD is developed and tested exclusively on Linux. Windows
and macOS GUI support is a best-effort community resource. Terminal mode
continues to work on all platforms with no additional setup.

---

### Feature — Automatic Layout Migration for New Blocks

When a new block is introduced, `layout.json` no longer needs to be manually
deleted. The grid engine now compares the saved layout against `DEFAULT_LAYOUT`
at startup, backfills any missing entries at their default positions, and
re-saves the file. Existing customised positions are preserved.

---

### Feature — Alerts Clear Button

A Clear button in the Alerts block drains the alert queue immediately without
waiting for the auto-dismiss timer.

---

### Feature — Ghost Drag and Resize

Block drag and resize operations now use a lightweight ghost overlay rather than
moving the real block during the gesture. Eliminates visual stutter on slow
redraws and makes large moves feel snappier.

---

### Feature — Data Contribution Plugins (EDDN, EDSM, EDAstro)

Opt-in journal uploading to three major community data networks:

- **EDDN** — market, outfitting, shipyard, and exploration data
- **EDSM** — flight log and discovery data
- **EDAstro** — exploration, organic scan, and carrier data

All three are disabled by default and configured under
`Preferences → Data & Integrations`. Each plugin maintains a disk-backed retry
queue so events are not lost on network failure.

---

### Bug Fix — Assets: Kestrel (active ship) missing from Ships tab

The Ships tab showed all stored ships but not the ship currently being flown.

Root cause: the background journal scan stopped at the first `StoredShips` event
found. That event is always recorded while the player is *in* a different ship,
so whichever ship was active at that moment is absent from it. If the currently-
active ship had been flown since the last `StoredShips` snapshot, it never
appeared.

Fix: the scan now accumulates a union of all `StoredShips` events across the
scan window (keyed by ShipID, taking the first occurrence of each hull). A
separate `Loadout` scan then identifies the current ship. The current ship is
stripped from the stored list by ShipID before display, guaranteeing it
appears only in the current-ship slot.

---

### Bug Fix — Assets: Duplicate hull in Ships tab after ship change

When switching ships, the previously-active hull appeared twice: once as the
current ship and again in the stored list.

Root cause: no ShipID was being captured from `Loadout` events, so there was no
way to identify and remove the current ship from the stored list when building
the display.

Fix: ShipID is now stored in `assets_current_ship["ship_id"]` and in each
stored ship dict. The display layer strips any stored entry whose ShipID matches
the current ship before combining the lists.

---

### Bug Fix — Assets: Shipyard.json parse failure (all ships missing on startup)

On startup, the ship type cache was never populated and no ships appeared in
the Ships tab until the player visited a shipyard during the session.

Root cause: `_read_shipyard_json()` iterated the file line by line and called
`json.loads()` on each line individually. `Shipyard.json` is a single multi-line
JSON object, so every parse attempt raised `ValueError` and was silently
swallowed. The cache was never written.

Fix: the reader now parses the whole file as a single object first and falls
back to line-by-line only if that fails, accommodating any future format change.

---

### Bug Fix — Assets: Race condition on startup (stored ships lost)

Stored ships loaded from `data.json` were occasionally overwritten with empty
lists on startup.

Root cause: the background journal scan thread was launched before
`_read_shipyard_json()` ran, leaving an empty ship-type cache when the scan
processed `StoredShips` events. In some timing windows the scan finished and
wrote empty state before the restore-from-storage path could set it correctly.

Fix: `_read_shipyard_json()` is now called in Step 1 of `on_load`, before the
background thread starts.

---

### Bug Fix — GTK warning: GtkButton finalised with GtkPopover child

```
Gtk-WARNING: Finalizing GtkButton, but it still has children left: GtkPopover
```

This warning was emitted during every Assets block refresh cycle when ship or
module rows were removed from the list.

Root cause: when a row is evicted from the list box, the `GtkButton` inside it
is finalized while the `GtkPopover` attached via `set_parent(btn)` is still
alive. GTK4 requires explicit `unparent()` before the parent is destroyed.

Fix: `container._popover.unparent()` is now called before `list_box.remove()`
in both the ship-row and module-row cleanup loops.

---

### Upgrading

No config changes required when upgrading from any 20260309x release.

If upgrading from 20260309b and EDSM or EDAstro were enabled during that
session, no events were successfully delivered (a serialisation bug in
20260309b prevented all sends). There is nothing to replay — both services
resume immediately on restart.

`layout.json` does not need to be deleted. New blocks are backfilled
automatically at their default positions.

---

### Known Limitations

- `StoredShips` and `StoredModules` data is stale between shipyard / outfitting
  visits — will be resolved by CAPI integration
- GTK4 GUI is Linux-native; Windows and macOS are best-effort
- CAPI integration is deferred (OAuth complexity)
- SLF shield state is not tracked — the game does not expose this via the
  journal or `Status.json`
- Block collapse state is not persisted across restarts — intentional for now
