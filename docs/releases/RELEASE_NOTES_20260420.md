# EDMD Release Notes

---

## 20260420

**Elite Dangerous Monitor Daemon — EDMD**

Cargo tracking overhaul fixing persistent stale items after transfers and
deliveries, fleet carrier cargo value and balance now visible in the Assets
block, fuel accuracy at login corrected, GTK4 OpenGL warning suppressed,
Colonisation plugin expanded with full Raven Colonial sync coverage including
fleet carrier cargo tracking and project completion notifications, and the
Colonisation block rebuilt with system-grouped collapsable projects.

---

### Fix — Cargo: Persistent Stale Items and Ghost Rows

Several independent defects combined to produce cargo items that survived
transfers and deliveries.

`CargoTransfer` was not subscribed. The game fires this event when cargo moves
between ship and carrier; without it, the hold was never updated and the
follow-up `Cargo` event (which the game writes with `Count` but no `Inventory`
after a transfer) fell through to reading `Cargo.json` from disk, which lagged
behind the journal by the time EDMD read it. `CargoTransfer` is now subscribed
and handled with a signed delta — `tocarrier` quantities are subtracted from
the ship hold and `toship` quantities are added back.

`Cargo Count=0` without an `Inventory` field was not clearing the hold. The
game fires `{"event":"Cargo","Count":0}` after all cargo is delivered to a
construction depot. The handler previously fell through to `_read_cargo_json()`
regardless. `Count=0` now unconditionally clears `cargo_items`.

In GTK4, the `"— empty —"` label was attached inside `Gtk.Grid` at the same
row used by data item rows. `Gtk.Grid.attach()` does not evict existing
occupants and `_clear_data_rows()` pruned item labels by grid coordinate but
left the empty label ghosted in the same cell. The empty label is now a sibling
widget placed outside the grid entirely. When `used == 0` it is shown and the
scroll widget is hidden; the two cannot interfere.

---

### Fix — Cargo: Fleet Carrier Market Poisoning Price Cache

`Market.json` is written by the game when the player opens the commodities
screen at any station, including their own fleet carrier. Fleet carrier market
files contain only active trade orders with `MeanPrice = 0`, not genuine market
data. EDMD was reading this file and caching the zero prices, causing all cargo
items to display `—` in the Sell and Avg columns for the remainder of the
session after any visit to the carrier market. `_read_cargo_json()` now returns
`None` when `StationType == "FleetCarrier"`.

---

### Fix — Cargo: Galactic Average Price Cache Never Persisted

The price cache was written to `mean_prices.json`, a filename absent from the
plugin storage allowlist in `core/plugin_loader.py`. The plugin raised
`ValueError` on every startup, prices were never loaded from the previous
session, and newly observed prices were never saved. The storage key is renamed
to `data.json`, consistent with every other plugin that uses persistent storage.

---

### Fix — Cargo: `cargo_items` Declared as List in MonitorState

`MonitorState.__init__` declared `self.cargo_items: list = []`. The cargo
plugin's `on_load` guard `if not hasattr(s, "cargo_items")` always evaluated
`False`, so `cargo_items` was never corrected to a `dict`. Every `.values()`
call in block rendering raised `AttributeError`. The declaration is corrected
to `dict = {}`.

---

### Feature — Assets Block: Carrier Balance in Wallet

The fleet carrier account balance is included in Frontier's statistics net
worth figure but was not shown as a line item in the Wallet tab. The gap
between visible assets and the net worth total was unexplained. **Balance** is
now a dedicated row in the Fleet Carrier section of the Wallet tab across all
three UIs, making the net worth arithmetic transparent.

---

### Feature — Assets Block: Fleet Carrier Cargo Section

The Fleet Carrier tab now includes a **Cargo** section showing stored units,
free hold space, and the galactic-average value of commodities actively listed
on the carrier market. The `FCMaterials` journal event was already subscribed
but the handler body was absent; it is now implemented so inventory value
updates immediately when the carrier commodity management screen is opened.
The Wallet tab's Fleet Carrier section also shows market listing value for
net-worth calculation purposes.

---

### Fix — Commander Block: Fuel Percentage Wrong at Login

`FuelLevel` and `FuelCapacity` are present in the `LoadGame` journal event but
the handler never read them. `fuel_current` was only updated by
`ReservoirReplenished`, which does not fire on every session start, leaving the
display at a stale value from the previous session until the player next
scooped or refuelled. Both fields are now read from `LoadGame` immediately,
handling the plain float form in that event as well as the `{"Main": N,
"Reserve": N}` dict form present in `Loadout`.

---

### Fix — GTK4: OpenGL Warning Suppressed at Startup

On many Linux configurations the GTK4 OpenGL scene graph renderer fails to
initialise and falls back to Cairo, printing a `gdk_gl_context_make_current()
failed` warning to stderr on every launch. `os.environ.setdefault("GSK_RENDERER",
"cairo")` is set before the `gi` import in `gui/app.py`, selecting Cairo from
the start. An explicit `GSK_RENDERER` in the environment before launch takes
precedence.

---

### Feature — Colonisation: Raven Colonial Sync Coverage Expanded

Several areas of the Raven Colonial API were unimplemented.

**Fleet carrier cargo tracking.** `CarrierStats`, `FCMaterials`,
`CargoTransfer`, `MarketBuy`, and `MarketSell` are now subscribed. When the
player's fleet carrier is linked on Raven Colonial, `CargoTransfer` events send
a signed incremental delta, `MarketBuy` at the carrier reduces FC stock,
`MarketSell` increases it, and `FCMaterials` sends a full authoritative
snapshot. At session start the current `FCMaterials` data is pushed as the
opening cargo baseline immediately after confirming the FC is linked.

**Project completion notification.** When `ColonisationConstructionComplete`
fires, or when `ColonisationConstructionDepot` reports `ConstructionComplete:
true`, EDMD looks up the project, strips the `"Orbital Construction Site: "` or
`"Planetary Construction Site: "` prefix from the build name via
`PATCH /api/project/{buildId}`, then marks the project complete via
`POST /api/project/{buildId}/complete`. Projects were previously remaining
as in-progress on the server indefinitely after the build finished.

**Batch completion checking.** The hourly background checker now calls
`GET /api/cmdr/{cmdr}` to retrieve all known projects in a single request and
matches them against locally tracked sites by market ID. Per-site fallback
polling is retained for sites absent from the commander response.

**`system_address` on every site dict.** The periodic checker previously used
`_current_system_address` for all lookups, so it could only verify sites in
the player's current system. Each site dict now stores its own `system_address`,
captured from `ColonisationSystemClaim` and from the `Docked` event that
precedes each `ColonisationConstructionDepot`. All sites across all systems are
checked every hour.

**Project creation API.** `create_project()` is now a public method on the
colonisation plugin, wrapping `PUT /api/project/` for future use.

---

### Feature — Colonisation Block: System Grouping and Collapsable Projects

The colonisation block now organises sites into a two-level collapsable tree
across all three UIs. Active sites are grouped under a collapsable system
header; each site header is independently collapsable beneath it. Both levels
default to expanded. The site name is rendered in the accent colour. Resource
rows are left-aligned with the site name. Done and failed sites remain as flat
single-line entries below the grouped active sites.

The previous GTK4 layout used `css_class="data-key"` on the collapse arrow
labels. The `.data-key` rule in `themes/base.css` carries `min-width: 80px`,
making each single-character arrow 80 pixels wide and producing the large gap
between arrow and text. Arrow labels are now plain `Gtk.Label` instances with
`set_size_request(14, -1)` and no CSS class.

---

### Files Changed

| File | Change |
|---|---|
| `core/data.py` | Dispatches `plugin_refresh("colonisation")` on `EP_FLEETCARRIER` CAPI poll |
| `core/electron_bridge.py` | `cargo_used` and `cargo_free` added to carrier dict; `assets_fc_materials` `None` guard |
| `core/plugin_loader.py` | `mean_prices.json` removed from storage allowlist; `data.json` is the correct key |
| `core/state.py` | `cargo_items` declaration corrected from `list = []` to `dict = {}` |
| `components/assets/plugin.py` | `FCMaterials` live event handler added; `None` guard on `assets_fc_materials` |
| `components/cargo/plugin.py` | `CargoTransfer` subscribed and handled; `Cargo Count=0` unconditionally clears hold; FC `Market.json` skipped; storage renamed to `data.json`; inline `Inventory` parsed directly from `Cargo` event |
| `components/colonisation/plugin.py` | `CarrierStats`, `FCMaterials`, `CargoTransfer`, `MarketBuy`, `MarketSell` subscribed; FC cargo sync; completion notification (`_raven_mark_complete`, `_raven_update_build_name`, `_notify_project_complete`); `_get_cmdr_projects()` batch checker; `system_address` on every site dict; `_patch()` and `_put()` HTTP primitives; `create_project()` public method |
| `components/commander/plugin.py` | `LoadGame` reads `FuelLevel` and `FuelCapacity` |
| `gui/app.py` | `os.environ.setdefault("GSK_RENDERER", "cairo")` before `gi` import |
| `gui/blocks/assets.py` | Carrier Balance row in Wallet; Cargo section in Fleet Carrier tab; `None` guards on `assets_fc_materials` |
| `gui/blocks/cargo.py` | `empty_lbl` moved outside grid; `used == 0` guard; FC market skip; `data.json` storage key |
| `gui/blocks/colonisation.py` | System grouping; two-level collapse; fixed-width arrow labels; resource rows aligned to site name |
| `tui/blocks/assets.py` | Carrier Balance row in Wallet; `None` guards on `assets_fc_materials` |
| `tui/blocks/cargo.py` | `used == 0` guard |
| `tui/blocks/colonisation.py` | System grouping; two-level collapse; resource indent corrected |
| `electron/renderer/src/components/AssetsBlock.vue` | Carrier Balance row in Wallet; Cargo section in Fleet Carrier tab |
| `electron/renderer/src/components/CargoBlock.vue` | `d.used === 0` guard |
| `electron/renderer/src/components/ColonisationBlock.vue` | System grouping; two-level collapse |

---

**Full changelog:** see commit history on the `electron` branch.
**Verification:** download `EDMD-20260420.sha256` and the corresponding `.sha256.sig` and verify with `ssh-keygen -Y verify`.
