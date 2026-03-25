# EDMD Release Notes

---

## 20260325

**Elite Dangerous Monitor Daemon — EDMD**

Major feature release. Introduces a persistent at-risk holdings tracker,
a completely redesigned Assets wallet, full on-foot and SRV commander state,
a comprehensive EDDN overhaul covering schema compliance and fleet carrier
market data, provider-aware 15-minute session summaries, and a set of NPC
crew block reliability fixes.

---

### Feature — At-Risk Holdings Tracker

A new persistent component (`core/components/holdings/`) tracks all value
held in-flight that would be lost on ship destruction. Unlike session activity
plugins, holdings survive session resets and accumulate across play sessions
until explicitly cashed out or cleared by death.

- **Bounty vouchers** — earned from `Bounty` events; redeemed per-faction
  from `RedeemVoucher` with broker percentage correction applied to recover
  the full face value cleared
- **Combat bonds** — same model as bounties; per-faction partial redemptions
  handled correctly
- **Trade vouchers** — same model
- **Cartography data** — tracked per-system in a dict keyed by system name,
  using the same value formula as the exploration activity plugin; sold systems
  removed exactly by name from `MultiSellExplorationData.Discovered`
- **Exobiology data** — tracked per-sample; matched by species key on
  `SellOrganicData`
- All buckets zeroed on `Died`. State persisted across restarts via plugin
  storage.

---

### Feature — Assets Block: Wallet Redesign

The Wallet tab is rebuilt with section headers matching the session summary
style. The separate "At Risk" tab is removed; its data now lives inline in
the Wallet.

**Currencies** — live credit balance.

**Fleet** — Ships value (hull + loadout sum from CAPI/journal), Modules value
(stored modules sum). Tab titles are now dynamic: **Ships (N)** and
**Modules (N)**.

**Fleet Carrier** — Hull shows the decommission return value (4,850,000,000 cr
for a Fleet Carrier; 24,850,000,000 cr for a Squadron Carrier, determined from
`CarrierStats.CarrierType`). Cargo shows the galactic average value of FC
materials. A Fredits row is reserved (hidden) for the upcoming Operations
currency.

**Assets At Risk** — Bounties, Combat bonds, Trade vouchers, Cartography
(est.), and Exobiology (est.) listed inline.

**Net Worth** — computed from Frontier's `Statistics` total (which covers
liquid credits, ships, modules, and carrier balance) plus cargo hold value,
FC cargo value, and at-risk holdings. Falls back to a computed sum before
`Statistics` fires.

The "Carrier" tab is renamed **Fleet Carrier** throughout in anticipation of
the Squadron Carrier.

---

### Feature — Commander Block: SRV and On-Foot State

The Commander block header and vitals now reflect the player's current vehicle.

**In SRV:**
- Header right shows the SRV type (e.g. `SRV SCARAB`)
- CMDR line appends `[IN SRV]`
- Shields shows `—` (SRVs have no shields)
- Hull shows SRV hull percentage, updated from `HullDamage` while in the SRV

**On foot:**
- Header right shows suit name (e.g. `ARTEMIS SUIT`); loadout name on line 2
  (e.g. `XBIO`)
- CMDR line appends `[ON FOOT]`
- Shields shows Up/Down from `ShieldState`, routed to suit shields
- Hull row label changes to **Health** and shows `—` (on-foot health requires
  Status.json polling, not yet implemented)

Events handled: `LaunchSRV`, `DockSRV`, `Disembark`, `Embark`, `SuitLoadout`.
All vehicle state resets on `LoadGame`.

---

### Enhancement — EDDN: Preload Guard

`Market`, `Outfitting`, `Shipyard`, `FCMaterials`, and `NavRoute` events are
now skipped during journal preload. These events all read from `.json` files
on disk that only reflect the current session. Replaying historical events
against stale files produced repeated MarketID mismatch errors in the log at
every startup.

---

### Enhancement — EDDN: Fleet Carrier Market

**Commodity market via `CarrierTradeOrder`.** When a buy or sell order is
set on the carrier's commodity market, EDDN now sends the updated Market.json
via `commodity/3`. The plugin tracks `_carrier_market_id` (from `CarrierStats`)
and `_docked_station_id` (from `Docked`) and only sends when confirmed docked
at the player's own carrier — resolving a MarketID mismatch that caused all
FC trade order triggers to be silently dropped.

**Bartender micro-resources via `fcmaterials_capi/1`.** When CAPI polls
`/market` for a fleet carrier, the `orders.onfootmicroresources` block
(populated when the Bartender service is enabled) is now forwarded to EDDN via
the `push_fcmaterials_capi` cross-plugin call — the same mechanism used for
Inara credit updates. If the Bartender is not enabled, this is a silent no-op.

**`fcmaterials_journal/1`** now reads `FCMaterials.json` from disk (the
authoritative source per EDDN spec) rather than the inline journal event data.

---

### Enhancement — EDDN: NavRoute

`navroute/1` messages are sent when `NavRoute` fires. The plugin reads
`NavRoute.json`, skips empty routes, and sends each hop's `StarSystem`,
`SystemAddress`, `StarPos`, and `StarClass`. A field name bug (`SystemName`
instead of `StarSystem`) has been corrected — the previous implementation
would have been rejected by EDDN on schema validation.

---

### Enhancement — EDDN: Schema Compliance

Several schema compliance gaps have been resolved against the canonical EDDN
live branch schema definitions:

- **Commodity** — items with `categoryname: NonMarketable` (limpets) and items
  with a non-empty `legality` field are now correctly excluded per the
  commodity README
- **Outfitting** — items with a non-null `sku` are now excluded unless the sku
  is `ELITE_HORIZONS_V_PLANETARY_LANDINGS`, per the outfitting README
- **CodexEntry** — validation relaxed to only require `System` and `EntryID`
  (the schema-defined required fields); the previous implementation dropped
  valid entries lacking `Region`, `Category`, or `SubCategory`
- **Blackmarket** — `blackmarket/1` removed; the schema has been deprecated
  since 2017, superseded by the `prohibited` array in `commodity/3`

---

### Fix — 15-Minute Session Summaries

The periodic summaries sent to terminal and Discord were not appearing for
non-combat sessions. The trigger condition required `active_session.kills > 0`,
so exploration, exobiology, mining, trade, and powerplay sessions produced no
output.

`emit_summary` is rewritten to use the activity provider system — the same
`get_summary_rows()` interface the GUI Summary tab uses. The trigger now fires
whenever any provider reports activity. Output mirrors the GUI Summary tab
exactly: duration at top, then a section per active plugin sorted
alphabetically by tab title. The `core` reference is threaded into the journal
monitoring loop to make the provider list accessible at the trigger site.

---

### Fix — NPC Crew Block: Hire Date and Amount Earned

Hire date, active duration, and total paid were always showing `—` after the
architecture refactor. Both `bootstrap_crew` and `bootstrap_slf` guard on
`state.has_fighter_bay` being `True` before scanning journals — but that flag
is only set by the `Loadout` event during preload, which runs after the
bootstrap phase has already completed. A new `bootstrap_fighter_bay()` pre-scan
reads the most recent `Loadout` event from journal history to set the flag
before other bootstraps run.

---

### Fix — NPC Crew Block: SLF Variant Label Alignment

The SLF variant name (e.g. "Gelid G") was appearing left-aligned in the header
instead of right-aligned. The rank label in `hdr_line2` carries `hexpand=True`
and acts as the horizontal spacer that pushes the variant label to the right.
When the crew has no combat rank, the code was hiding the rank label entirely,
collapsing the space. The rank label is now always present (empty string when
no rank) so the layout is preserved regardless of rank status.

---

### Fix — NPC Crew Block: SLF Variant Name After Bootstrap

After the `bootstrap_fighter_bay` fix, `bootstrap_slf` could now run but
sometimes recovered a bare type name (e.g. `GU-97` with no variant) when the
journal `RestockVehicle` event lacked a `Loadout` field. The crew_slf plugin's
detailed journal scan — which tracks `ShipID` to match the correct vessel — was
only triggered when `slf_type is None`. The condition now also triggers when the
type lacks a `(variant)` component, ensuring the scan runs and recovers the
full name (e.g. `GU-97 (Gelid G)`).

---

### Fix — Assets Block: Cargo Crash

A `TypeError` was raised during the net worth calculation when `cargo_items`
contained non-dict entries. The iteration now guards with `isinstance(item, dict)`.

---

### Fix — Startup SyntaxError

A spurious `import time` statement was prepended before `from __future__ import
annotations` in `core/data.py`, causing a `SyntaxError` at startup. Removed.

