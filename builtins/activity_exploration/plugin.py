"""
builtins/activity_exploration/plugin.py — Exploration session tracking.

Tracks FSD jumps and distance, FSS/DSS scans, estimated unsold scan value
(accumulated from Scan events using Frontier's body value formula), and
realised cartography sale value split into base + discovery bonus.

Body value formula (from Frontier community research, forums.frontier.co.uk):
  Base = k + (3 * k * mass^0.199977 / 5.3)
  Terraformable bonus = k_terra + (3 * k_terra * mass^0.199977 / 5.3)  [added on top]
  Star  = k + (solar_mass * k / 66.25)

Multipliers:
  First discovered:  2.5× scan value
  Mapped (Odyssey):  3.3 × 1.3 = 4.29× scan value
  First mapped:      same 4.29× on mapped component
  Efficiency bonus:  1.25× mapped value

Tab title: Exploration
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits

# ── Planet k-factors ──────────────────────────────────────────────────────────
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

# Additional k added for terraformable planets
_TERRA_K: dict[str, int] = {
    "high metal content body":  241607,
    "water world":              279088,
    "earthlike body":           279088,
    "rocky body":               223971,
}

# Star k-factors
_STAR_K: dict[str, int] = {
    "black hole":   54309,
    "neutron star": 54309,
    "white dwarf":  33737,
}
_STAR_K_DEFAULT = 2880

# Multipliers
_FIRST_DISC_MULT    = 2.5
_MAP_MULT           = 3.3 * 1.3   # 4.29 — base map × Odyssey 30% bonus
_EFFICIENCY_MULT    = 1.25
_FIRST_MAPPED_MULT  = _MAP_MULT    # same factor, separate component


def _planet_base(planet_class: str, mass_em: float) -> int:
    pc = planet_class.lower().strip()
    k  = _PLANET_K.get(pc, _PLANET_K_DEFAULT)
    return round(k + (3 * k * (mass_em ** 0.199977) / 5.3))


def _terra_bonus(planet_class: str, mass_em: float) -> int:
    pc = planet_class.lower().strip()
    kt = _TERRA_K.get(pc, 0)
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
    """Estimate total credit value of a body scan + optional DSS."""
    terraformable = bool(terraform_state and terraform_state.lower()
                         not in ("", "not terraformable"))
    base  = _planet_base(planet_class, mass_em)
    bonus = _terra_bonus(planet_class, mass_em) if terraformable else 0
    scan_val = base + bonus

    value = round(scan_val * _FIRST_DISC_MULT) if not was_discovered else scan_val

    if dss_mapped:
        map_val = round(scan_val * _MAP_MULT)
        if not was_mapped:
            map_val = round(map_val)   # first-mapped uses same mult on base
        if efficient:
            map_val = round(map_val * _EFFICIENCY_MULT)
        value += map_val

    return value


class ActivityExplorationPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME        = "activity_exploration"
    PLUGIN_DISPLAY     = "Exploration Activity"
    PLUGIN_VERSION     = "1.2.0"
    PLUGIN_DESCRIPTION = "Tracks jumps, distance, bodies scanned, and scan value."
    ACTIVITY_TAB_TITLE = "Exploration"

    SUBSCRIBED_EVENTS = [
        "FSDJump",
        "Scan",
        "SAAScanComplete",
        "SellExplorationData",
        "MultiSellExplorationData",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.jumps:               int   = 0
        self.distance_ly:         float = 0.0
        self.bodies_fss_scanned:  int   = 0
        self.bodies_dss_mapped:   int   = 0
        self.first_discoveries:   int   = 0
        self.first_mapped:        int   = 0
        self.unsold_value_est:    int   = 0
        self.cartography_base:    int   = 0
        self.cartography_bonus:   int   = 0
        self.session_start_time         = None
        # Pending DSS data: body_id → scan info dict
        self._pending_scans: dict       = {}

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")
        gq      = self.core.gui_queue

        match ev:

            case "FSDJump":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.jumps       += 1
                self.distance_ly += event.get("JumpDist", 0.0)
                if gq:
                    gq.put(("stats_update", None))

            case "Scan":
                scan_type = event.get("ScanType", "")
                if scan_type not in ("AutoScan", "Detailed", ""):
                    return

                if self.session_start_time is None:
                    self.session_start_time = logtime

                planet_class    = event.get("PlanetClass", "")
                star_type       = event.get("StarType", "")
                was_discovered  = event.get("WasDiscovered", True)
                was_mapped      = event.get("WasMapped", True)
                terraform_state = event.get("TerraformState", "")
                body_id         = event.get("BodyID")

                if planet_class:
                    mass_em = event.get("MassEM", 1.0) or 1.0
                    self.bodies_fss_scanned += 1
                    if not was_discovered:
                        self.first_discoveries += 1

                    val = _scan_value(planet_class, mass_em, terraform_state,
                                      was_discovered, was_mapped,
                                      dss_mapped=False, efficient=False)
                    self.unsold_value_est += val

                    if body_id is not None:
                        self._pending_scans[body_id] = {
                            "planet_class":    planet_class,
                            "mass_em":         mass_em,
                            "terraform_state": terraform_state,
                            "was_discovered":  was_discovered,
                            "was_mapped":      was_mapped,
                            "scan_value":      val,
                        }

                elif star_type:
                    solar_mass = event.get("StellarMass", 1.0) or 1.0
                    star_val   = _star_value(star_type, solar_mass)
                    if not was_discovered:
                        star_val = round(star_val * _FIRST_DISC_MULT)
                        self.first_discoveries += 1
                    self.unsold_value_est += star_val

            case "SAAScanComplete":
                body_id   = event.get("BodyID")
                target    = event.get("EfficiencyTarget", 99)
                used      = event.get("ProbesUsed", 99)
                efficient = (used <= target)
                self.bodies_dss_mapped += 1

                pending = self._pending_scans.get(body_id)
                if pending:
                    full_val = _scan_value(
                        pending["planet_class"], pending["mass_em"],
                        pending["terraform_state"],
                        pending["was_discovered"], pending["was_mapped"],
                        dss_mapped=True, efficient=efficient,
                    )
                    # Add only the DSS increment (scan portion already counted)
                    self.unsold_value_est += full_val - pending["scan_value"]
                    if not pending["was_mapped"]:
                        self.first_mapped += 1

            case "SellExplorationData":
                base  = event.get("BaseValue", 0)
                bonus = event.get("Bonus", 0)
                total = event.get("TotalEarnings", 0) or (base + bonus)
                self.cartography_base  += base
                self.cartography_bonus += bonus
                self.unsold_value_est   = max(0, self.unsold_value_est - total)
                if gq:
                    gq.put(("stats_update", None))

            case "MultiSellExplorationData":
                base  = event.get("BaseValue", 0)
                bonus = event.get("Bonus", 0)
                total = event.get("TotalEarnings", 0) or (base + bonus)
                self.cartography_base  += base
                self.cartography_bonus += bonus
                self.unsold_value_est   = max(0, self.unsold_value_est - total)
                if gq:
                    gq.put(("stats_update", None))

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.jumps > 0 or self.bodies_fss_scanned > 0

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.jumps > 0:
            rows.append({
                "label": "Distance",
                "value": f"{self.jumps} jumps",
                "rate":  f"{self.distance_ly:,.0f} ly",
            })
        if self.bodies_fss_scanned > 0:
            carto_rate = fmt_credits(self.unsold_value_est) if self.unsold_value_est > 0 else None
            rows.append({
                "label": "Bodies scanned",
                "value": str(self.bodies_fss_scanned),
                "rate":  carto_rate,
            })
        total_sold = self.cartography_base + self.cartography_bonus
        if total_sold > 0:
            rows.append({
                "label": "Cartography sold",
                "value": fmt_credits(total_sold),
                "rate":  None,
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.bodies_dss_mapped > 0:
            rows.append({"label": "DSS mapped",        "value": str(self.bodies_dss_mapped),  "rate": None})
        if self.first_discoveries > 0:
            rows.append({"label": "First discoveries", "value": str(self.first_discoveries),  "rate": None})
        if self.first_mapped > 0:
            rows.append({"label": "First mapped",      "value": str(self.first_mapped),       "rate": None})
        if self.cartography_bonus > 0:
            rows.append({"label": "  Discovery bonus", "value": fmt_credits(self.cartography_bonus), "rate": None})
        return rows
