"""
core/components/holdings/plugin.py — At-risk holdings tracker.

Self-contained: subscribes directly to journal events, no dependency on
activity plugins. Holdings have a different lifetime to session plugins —
they accumulate until explicitly cashed out or lost on death.

Tracking:
  Bounty vouchers   — earned: Bounty; redeemed: RedeemVoucher(bounty)
  Combat bonds      — earned: FactionKillBond; redeemed: RedeemVoucher(CombatBond)
  Trade vouchers    — earned: TradeVoucher; redeemed: RedeemVoucher(trade)
  Cartography data  — per-system dict; matched by SystemName on sell
  Exobiology data   — per-sample list; matched by Species key on sell

Vouchers are redeemed faction-by-faction — subtract the face value redeemed.
Cartography is sold per-system — pop sold systems from the dict exactly.
Exobiology is sold per-sample — pop matched samples from the list.
All buckets zeroed on Died.

PowerPlay bonuses affect the actual payout vs our estimate but cannot be
predicted in advance; the display notes that cartography values are estimates.
"""

from core.plugin_loader import BasePlugin


# ── Exobiology species value table ────────────────────────────────────────────
_SPECIES_VALUE: dict[str, int] = {
    "$Codex_Ent_Aleoids_01_Name;": 7252500,
    "$Codex_Ent_Aleoids_02_Name;": 6284600,
    "$Codex_Ent_Aleoids_05_Name;": 12934900,
    "$Codex_Ent_Aleoids_04_Name;": 3385200,
    "$Codex_Ent_Aleoids_03_Name;": 3385200,
    "$Codex_Ent_Sphere_Name;": 1629700,
    "$Codex_Ent_Vents_Name;": 1628800,
    "$Codex_Ent_TubeABCD_01_Name;": 1514500,
    "$Codex_Ent_TubeABCD_02_Name;": 1514500,
    "$Codex_Ent_TubeABCD_03_Name;": 1514500,
    "$Codex_Ent_TubeABCD_04_Name;": 1514500,
    "$Codex_Ent_TubeABCD_05_Name;": 1514500,
    "$Codex_Ent_TubeABCD_06_Name;": 1514500,
    "$Codex_Ent_TubeABCD_07_Name;": 1514500,
    "$Codex_Ent_Cone_Name;": 1471900,
    "$Codex_Ent_Bacterium_01_Name;": 1000200,
    "$Codex_Ent_Bacterium_07_Name;": 1658500,
    "$Codex_Ent_Bacterium_12_Name;": 1000200,
    "$Codex_Ent_Bacterium_02_Name;": 1152500,
    "$Codex_Ent_Bacterium_03_Name;": 1689800,
    "$Codex_Ent_Bacterium_06_Name;": 8418000,
    "$Codex_Ent_Bacterium_04_Name;": 5289900,
    "$Codex_Ent_Bacterium_08_Name;": 4638900,
    "$Codex_Ent_Bacterium_05_Name;": 4934500,
    "$Codex_Ent_Bacterium_11_Name;": 1949000,
    "$Codex_Ent_Bacterium_10_Name;": 3897000,
    "$Codex_Ent_Bacterium_09_Name;": 1000200,
    "$Codex_Ent_Bacterium_13_Name;": 7774700,
    "$Codex_Ent_Cactoid_01_Name;": 3667600,
    "$Codex_Ent_Cactoid_05_Name;": 2483600,
    "$Codex_Ent_Cactoid_04_Name;": 2483600,
    "$Codex_Ent_Cactoid_02_Name;": 3667600,
    "$Codex_Ent_Cactoid_03_Name;": 16202800,
    "$Codex_Ent_Clypeus_01_Name;": 8418000,
    "$Codex_Ent_Clypeus_03_Name;": 11873200,
    "$Codex_Ent_Clypeus_02_Name;": 16202800,
    "$Codex_Ent_Conchas_01_Name;": 7774700,
    "$Codex_Ent_Conchas_04_Name;": 16777215,
    "$Codex_Ent_Conchas_02_Name;": 2352400,
    "$Codex_Ent_Conchas_03_Name;": 4572400,
    "$Codex_Ent_Electricae_01_Name;": 6284600,
    "$Codex_Ent_Electricae_02_Name;": 6284600,
    "$Codex_Ent_Fonticulus_06_Name;": 1000200,
    "$Codex_Ent_Fonticulus_04_Name;": 3111000,
    "$Codex_Ent_Fonticulus_05_Name;": 20000000,
    "$Codex_Ent_Fonticulus_03_Name;": 5727600,
    "$Codex_Ent_Fonticulus_01_Name;": 19010800,
    "$Codex_Ent_Fonticulus_02_Name;": 1000000,
    "$Codex_Ent_Shrubs_01_Name;": 7774700,
    "$Codex_Ent_Shrubs_05_Name;": 1639800,
    "$Codex_Ent_Shrubs_02_Name;": 1639800,
    "$Codex_Ent_Shrubs_07_Name;": 1639800,
    "$Codex_Ent_Shrubs_04_Name;": 10326000,
    "$Codex_Ent_Shrubs_06_Name;": 1639800,
    "$Codex_Ent_Shrubs_03_Name;": 5988900,
    "$Codex_Ent_Fumerolas_01_Name;": 6284600,
    "$Codex_Ent_Fumerolas_04_Name;": 6284600,
    "$Codex_Ent_Fumerolas_02_Name;": 16202800,
    "$Codex_Ent_Fumerolas_03_Name;": 7774700,
    "$Codex_Ent_Fungoids_03_Name;": 3703200,
    "$Codex_Ent_Fungoids_01_Name;": 3330300,
    "$Codex_Ent_Fungoids_04_Name;": 1670100,
    "$Codex_Ent_Fungoids_02_Name;": 2680300,
    "$Codex_Ent_Osseus_01_Name;": 1483000,
    "$Codex_Ent_Osseus_03_Name;": 12934900,
    "$Codex_Ent_Osseus_02_Name;": 4027800,
    "$Codex_Ent_Osseus_05_Name;": 9739000,
    "$Codex_Ent_Osseus_06_Name;": 3156300,
    "$Codex_Ent_Osseus_04_Name;": 2404700,
    "$Codex_Ent_Ingensradices_Unicus_Name;": 119037,
    "$Codex_Ent_Recepta_01_Name;": 14313700,
    "$Codex_Ent_Recepta_03_Name;": 16202800,
    "$Codex_Ent_Recepta_02_Name;": 12934900,
    "$Codex_Ent_Seed_Name;": 1593700,
    "$Codex_Ent_Shard_Name;": 1515200,
    "$Codex_Ent_Stratum_01_Name;": 2448900,
    "$Codex_Ent_Stratum_02_Name;": 1362000,
    "$Codex_Ent_Stratum_03_Name;": 2788300,
    "$Codex_Ent_Stratum_04_Name;": 2448900,
    "$Codex_Ent_Stratum_05_Name;": 1362000,
    "$Codex_Ent_Stratum_06_Name;": 16202800,
    "$Codex_Ent_Stratum_07_Name;": 19010800,
    "$Codex_Ent_Stratum_08_Name;": 2637500,
    "$Codex_Ent_Tube_01_Name;": 11873200,
    "$Codex_Ent_Tube_04_Name;": 7774700,
    "$Codex_Ent_Tube_02_Name;": 2415500,
    "$Codex_Ent_Tube_03_Name;": 2637500,
    "$Codex_Ent_Tube_05_Name;": 5853800,
    "$Codex_Ent_Tussocks_15_Name;": 3252500,
    "$Codex_Ent_Tussocks_06_Name;": 7025800,
    "$Codex_Ent_Tussocks_02_Name;": 3472400,
    "$Codex_Ent_Tussocks_11_Name;": 1766600,
    "$Codex_Ent_Tussocks_08_Name;": 1766600,
    "$Codex_Ent_Tussocks_10_Name;": 1766600,
    "$Codex_Ent_Tussocks_05_Name;": 1849000,
    "$Codex_Ent_Tussocks_04_Name;": 1766600,
    "$Codex_Ent_Tussocks_01_Name;": 1000200,
    "$Codex_Ent_Tussocks_07_Name;": 1000200,
    "$Codex_Ent_Tussocks_03_Name;": 1000200,
    "$Codex_Ent_Tussocks_09_Name;": 4447100,
    "$Codex_Ent_Tussocks_12_Name;": 19010800,
    "$Codex_Ent_Tussocks_13_Name;": 7774700,
    "$Codex_Ent_Tussocks_14_Name;": 3227700,
    "$Codex_Ent_Tussocks_16_Name;": 14313700,
}

_FIRST_DISC_MULT = 5
_FOOTFALL_MULT   = 4


def _exobio_value(species_key: str, was_logged: bool, footfall_bonus: bool) -> int:
    base = _SPECIES_VALUE.get(species_key, 0)
    if not base:
        return 0
    value = base * _FIRST_DISC_MULT if not was_logged else base
    if footfall_bonus:
        value += base * _FOOTFALL_MULT
    return value


# ── Cartography value formula ─────────────────────────────────────────────────
_PLANET_K: dict[str, int] = {
    "metal rich body":             52292,
    "ammonia world":              232619,
    "sudarsky class i gas giant":   3974,
    "sudarsky class ii gas giant": 23168,
    "high metal content body":     23168,
    "water world":                155581,
    "earthlike body":             155581,
}
_PLANET_K_DEFAULT = 720

_TERRA_K: dict[str, int] = {
    "high metal content body":  241607,
    "water world":              279088,
    "earthlike body":           279088,
    "rocky body":               223971,
}

_STAR_K: dict[str, int] = {
    "black hole":   54309,
    "neutron star": 54309,
    "white dwarf":  33737,
}
_STAR_K_DEFAULT = 2880

_FIRST_DISC_SCAN = 2.5
_MAP_MULT        = 3.3 * 1.3
_EFFICIENCY_MULT = 1.25


def _planet_base(planet_class: str, mass_em: float) -> int:
    k = _PLANET_K.get(planet_class.lower().strip(), _PLANET_K_DEFAULT)
    return round(k + (3 * k * (mass_em ** 0.199977) / 5.3))


def _terra_bonus(planet_class: str, mass_em: float) -> int:
    kt = _TERRA_K.get(planet_class.lower().strip(), 0)
    if not kt:
        return 0
    return round(kt + (3 * kt * (mass_em ** 0.199977) / 5.3))


def _star_value(star_type: str, solar_mass: float) -> int:
    st = star_type.lower()
    k  = next((v for key, v in _STAR_K.items() if key in st), _STAR_K_DEFAULT)
    return round(k + (solar_mass * k / 66.25))


def _scan_value(planet_class: str, mass_em: float, terraform_state: str,
                was_discovered: bool, was_mapped: bool,
                dss_mapped: bool, efficient: bool) -> int:
    terraformable = bool(
        terraform_state and
        terraform_state.lower() not in ("", "not terraformable")
    )
    base     = _planet_base(planet_class, mass_em)
    bonus    = _terra_bonus(planet_class, mass_em) if terraformable else 0
    scan_val = base + bonus
    value    = round(scan_val * _FIRST_DISC_SCAN) if not was_discovered else scan_val
    if dss_mapped:
        map_val = round(scan_val * _MAP_MULT)
        if efficient:
            map_val = round(map_val * _EFFICIENCY_MULT)
        value += map_val
    return value


# ── Plugin ────────────────────────────────────────────────────────────────────

class HoldingsPlugin(BasePlugin):
    PLUGIN_NAME    = "holdings"
    PLUGIN_DISPLAY = "At-Risk Holdings"
    PLUGIN_DESCRIPTION = (
        "Tracks unredeemed vouchers, bonds, and unsold data "
        "that would be lost on ship destruction."
    )
    PLUGIN_VERSION = "1.2.0"

    SUBSCRIBED_EVENTS = [
        "Bounty",
        "FactionKillBond",
        "TradeVoucher",
        "RedeemVoucher",
        "Scan",
        "SAAScanComplete",
        "SellExplorationData",
        "MultiSellExplorationData",
        "ScanOrganic",
        "SellOrganicData",
        "Died",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        # Per-system cartography: {system_name: estimated_value}
        self._carto: dict[str, int] = {}
        # Per-sample exobiology: list of {species: key, value: int, ts: str}
        self._exobio: list[dict] = []
        # Pending DSS: body_id → scan info
        self._pending: dict = {}
        # Dedup sets — prevent double-counting on journal preload replay
        self._seen_bodies:  set[tuple] = set()   # (system, body_id)
        self._seen_exobio:  set[str]   = set()   # event timestamp strings
        # Current system name (from FSDJump/Location via state)
        self._restore()

    def _restore(self) -> None:
        data  = self.storage.read_json() or {}
        state = self.core.state

        # Vouchers — simple ints
        state.holdings_bounties = data.get("bounties", 0)
        state.holdings_bonds    = data.get("bonds",    0)
        state.holdings_trade    = data.get("trade",    0)

        # Cartography — per-system dict
        self._carto = data.get("cartography", {})
        state.holdings_cartography = sum(self._carto.values())

        # Exobiology — per-sample list
        self._exobio = data.get("exobiology", [])
        state.holdings_exobiology = sum(s["value"] for s in self._exobio)

        # Rebuild dedup sets from persisted data so preload cannot re-add
        # entries that survived from a previous session.
        self._seen_bodies = {tuple(b) for b in data.get("seen_bodies", [])}
        self._seen_exobio = set(data.get("seen_exobio", []))

    def _persist(self) -> None:
        state = self.core.state
        self.storage.write_json({
            "bounties":    state.holdings_bounties,
            "bonds":       state.holdings_bonds,
            "trade":       state.holdings_trade,
            "cartography": self._carto,
            "exobiology":  self._exobio,
            "seen_bodies": list(self._seen_bodies),
            "seen_exobio": list(self._seen_exobio),
        })

    def _update_carto_state(self) -> None:
        self.core.state.holdings_cartography = sum(self._carto.values())

    def _update_exobio_state(self) -> None:
        self.core.state.holdings_exobiology = sum(s["value"] for s in self._exobio)

    def _notify(self) -> None:
        gq = self.core.gui_queue
        if gq:
            gq.put(("holdings_update", None))

    def _current_system(self) -> str:
        return getattr(self.core.state, "current_system", "") or ""

    def on_event(self, event: dict, state) -> None:
        ev = event.get("event")

        match ev:

            # ── Voucher / bond accumulation ───────────────────────────────

            case "Bounty":
                reward = event.get("TotalReward", 0) or event.get("Reward", 0)
                state.holdings_bounties += reward
                self._persist(); self._notify()

            case "FactionKillBond":
                state.holdings_bonds += event.get("Reward", 0)
                self._persist(); self._notify()

            case "TradeVoucher":
                state.holdings_trade += event.get("Reward", 0)
                self._persist(); self._notify()

            case "RedeemVoucher":
                # Redemptions are per-faction / per-station — subtract the
                # face value actually cleared. BrokerPercentage means we
                # received less than face value, but the full amount is gone.
                vtype  = event.get("Type", "")
                amount = event.get("Amount", 0)
                pct    = event.get("BrokerPercentage", 0.0)
                face   = round(amount / (1.0 - pct / 100.0)) if pct else amount
                match vtype:
                    case "bounty":
                        state.holdings_bounties = max(0, state.holdings_bounties - face)
                    case "CombatBond":
                        state.holdings_bonds = max(0, state.holdings_bonds - face)
                    case "trade":
                        state.holdings_trade = max(0, state.holdings_trade - face)
                self._persist(); self._notify()

            # ── Cartography accumulation (per-system) ─────────────────────

            case "Scan":
                scan_type = event.get("ScanType", "")
                if scan_type not in ("AutoScan", "Detailed", ""):
                    return
                system = event.get("StarSystem", "") or self._current_system()
                if not system:
                    return

                planet_class    = event.get("PlanetClass", "")
                star_type       = event.get("StarType", "")
                was_discovered  = event.get("WasDiscovered", True)
                was_mapped      = event.get("WasMapped", True)
                terraform_state = event.get("TerraformState", "")
                body_id         = event.get("BodyID")

                if planet_class:
                    body_key = (system, body_id)
                    if body_id is not None and body_key in self._seen_bodies:
                        return   # already counted this body
                    mass_em = event.get("MassEM", 1.0) or 1.0
                    val = _scan_value(planet_class, mass_em, terraform_state,
                                      was_discovered, was_mapped,
                                      dss_mapped=False, efficient=False)
                    self._carto[system] = self._carto.get(system, 0) + val
                    if body_id is not None:
                        self._seen_bodies.add(body_key)
                        self._pending[body_id] = {
                            "system":          system,
                            "planet_class":    planet_class,
                            "mass_em":         mass_em,
                            "terraform_state": terraform_state,
                            "was_discovered":  was_discovered,
                            "was_mapped":      was_mapped,
                            "scan_value":      val,
                        }
                    self._update_carto_state(); self._persist(); self._notify()

                elif star_type:
                    body_key = (system, body_id)
                    if body_id is not None and body_key in self._seen_bodies:
                        return   # already counted this star
                    solar_mass = event.get("StellarMass", 1.0) or 1.0
                    star_val   = _star_value(star_type, solar_mass)
                    if not was_discovered:
                        star_val = round(star_val * _FIRST_DISC_SCAN)
                    self._carto[system] = self._carto.get(system, 0) + star_val
                    if body_id is not None:
                        self._seen_bodies.add(body_key)
                    self._update_carto_state(); self._persist(); self._notify()

            case "SAAScanComplete":
                body_id   = event.get("BodyID")
                target    = event.get("EfficiencyTarget", 99)
                used      = event.get("ProbesUsed", 99)
                efficient = (used <= target)
                pending   = self._pending.get(body_id)
                # _pending is consumed on first SAAScanComplete — replay
                # of the same event finds no pending entry and skips.
                if pending:
                    system   = pending["system"]
                    full_val = _scan_value(
                        pending["planet_class"], pending["mass_em"],
                        pending["terraform_state"],
                        pending["was_discovered"], pending["was_mapped"],
                        dss_mapped=True, efficient=efficient,
                    )
                    delta = full_val - pending["scan_value"]
                    self._carto[system] = self._carto.get(system, 0) + delta
                    self._update_carto_state(); self._persist(); self._notify()

            case "SellExplorationData":
                # Legacy single-sell — system name in "System" field
                system = event.get("System", "")
                if system and system in self._carto:
                    del self._carto[system]
                    self._pending = {
                        k: v for k, v in self._pending.items()
                        if v.get("system") != system
                    }
                    # Allow re-scanning the same bodies if player returns
                    self._seen_bodies = {
                        b for b in self._seen_bodies if b[0] != system
                    }
                    self._update_carto_state(); self._persist(); self._notify()

            case "MultiSellExplorationData":
                # Exact per-system removal — Discovered lists every sold system
                changed = False
                for entry in event.get("Discovered", []):
                    system = entry.get("SystemName", "")
                    if system and system in self._carto:
                        del self._carto[system]
                        changed = True
                if changed:
                    sold = {e.get("SystemName","") for e in event.get("Discovered",[])}
                    self._pending = {
                        k: v for k, v in self._pending.items()
                        if v.get("system") not in sold
                    }
                    # Allow re-scanning the same bodies if player returns
                    self._seen_bodies = {
                        b for b in self._seen_bodies if b[0] not in sold
                    }
                    self._update_carto_state(); self._persist(); self._notify()

            # ── Exobiology accumulation (per-sample) ─────────────────────

            case "ScanOrganic":
                if event.get("ScanType") != "Analyse":
                    return
                # Deduplicate by timestamp — each analysis has a unique timestamp.
                # Same species from different planets produces different timestamps.
                ts = event.get("timestamp", "")
                if ts and ts in self._seen_exobio:
                    return   # already counted this analysis event
                species_key    = event.get("Species", "")
                was_logged     = bool(event.get("WasLogged", True))
                footfall_bonus = (event.get("WasFootfalled") is False)
                val = _exobio_value(species_key, was_logged, footfall_bonus)
                self._exobio.append({"species": species_key, "value": val, "ts": ts})
                if ts:
                    self._seen_exobio.add(ts)
                self._update_exobio_state(); self._persist(); self._notify()

            case "SellOrganicData":
                # BioData lists each sold sample with Species and Value.
                # Match per-sample: for each sold item, remove the first
                # held entry with that species key and clear its timestamp
                # from the seen set so a future re-scan of the same species
                # is counted correctly.
                for item in event.get("BioData", []):
                    species = item.get("Species", "")
                    for i, held in enumerate(self._exobio):
                        if held.get("species") == species:
                            ts = held.get("ts", "")
                            if ts:
                                self._seen_exobio.discard(ts)
                            self._exobio.pop(i)
                            break
                self._update_exobio_state(); self._persist(); self._notify()

            # ── Ship destruction ──────────────────────────────────────────

            case "Died":
                state.holdings_bounties = 0
                state.holdings_bonds    = 0
                state.holdings_trade    = 0
                self._carto.clear()
                self._exobio.clear()
                self._pending.clear()
                self._seen_bodies.clear()
                self._seen_exobio.clear()
                self._update_carto_state()
                self._update_exobio_state()
                self._persist(); self._notify()

    def total_at_risk(self) -> int:
        state = self.core.state
        return (
            state.holdings_bounties
            + state.holdings_bonds
            + state.holdings_trade
            + state.holdings_cartography
            + state.holdings_exobiology
        )
