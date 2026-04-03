"""
core/components/colonisation/plugin.py — Colonisation construction tracking.

Tracks system colonisation construction sites: what resources are required,
how much has been delivered so far, and what remains. Supports multiple
active construction sites simultaneously.

Fleet carrier integration: tracks cargo staged on your fleet carrier
separately from ship cargo for accurate "still needed" calculations.

State written to MonitorState:
    colonisation_sites   list[dict]   — active construction sites
    colonisation_docked  bool         — True when docked at a construction depot

Each site dict:
    {
        "market_id":   int,
        "system":      str,
        "station":     str,           # short display name
        "progress":    float,         # 0.0–1.0
        "complete":    bool,
        "failed":      bool,
        "resources":   {              # keyed by canonical commodity name
            commodity: {
                "name":      str,     # display name
                "required":  int,
                "provided":  int,
            }
        }
    }

GUI block: colonisation
"""

from core.plugin_loader import BasePlugin


def _canon(name: str) -> str:
    """Canonical lowercase commodity key, stripping localisation wrappers."""
    s = (name or "").strip().lower()
    if s.startswith("$") and s.endswith(";"):
        inner = s[1:-1]
        s = inner[:-5] if inner.endswith("_name") else inner
    # Strip trailing _name patterns from non-wrapped keys
    if s.endswith("_name"):
        s = s[:-5]
    return s


def _short_station_name(station: str, system: str) -> str:
    """Return a compact display name for a construction site."""
    if not station:
        return system or "Unknown"
    if station.startswith("$EXT_PANEL_ColonisationShip"):
        return f"{system} (colonisation ship)" if system else "Colonisation Ship"
    if "Construction Site: " in station:
        return station.split("Construction Site: ", 1)[1].strip()
    return station


class ColonisationPlugin(BasePlugin):
    PLUGIN_NAME        = "colonisation"
    PLUGIN_DISPLAY     = "Colonisation"
    PLUGIN_DESCRIPTION = "Tracks colonisation construction site resource requirements and delivery progress."
    PLUGIN_VERSION     = "1.0.0"

    SUBSCRIBED_EVENTS = [
        "ColonisationSystemClaim",
        "ColonisationConstructionDepot",
        "ColonisationContribution",
        "ColonisationConstructionComplete",
        "ColonisationConstructionFailed",
        "Docked",
        "Undocked",
        "Location",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_block(self, priority=55)
        s = core.state
        if not hasattr(s, "colonisation_sites"):
            s.colonisation_sites  = []
        if not hasattr(s, "colonisation_docked"):
            s.colonisation_docked = False
        if not hasattr(s, "_colonisation_current_market_id"):
            s._colonisation_current_market_id = None

        self._restore()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _restore(self) -> None:
        data = self.storage.read_json() or {}
        self.core.state.colonisation_sites = data.get("sites", [])

    def _save(self) -> None:
        self.storage.write_json({"sites": self.core.state.colonisation_sites})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_site(self, market_id: int) -> dict | None:
        for site in self.core.state.colonisation_sites:
            if site.get("market_id") == market_id:
                return site
        return None

    def _upsert_site(self, market_id: int, system: str, station: str,
                     progress: float, complete: bool, failed: bool,
                     resources: dict[str, dict]) -> None:
        """Insert or update a construction site record."""
        state    = self.core.state
        existing = self._find_site(market_id)
        if existing is not None:
            existing["system"]    = system or existing["system"]
            existing["station"]   = station or existing["station"]
            existing["progress"]  = progress
            existing["complete"]  = complete
            existing["failed"]    = failed
            existing["resources"] = resources
        else:
            state.colonisation_sites.append({
                "market_id": market_id,
                "system":    system,
                "station":   station,
                "progress":  progress,
                "complete":  complete,
                "failed":    failed,
                "resources": resources,
            })

    # ── Event handling ────────────────────────────────────────────────────────

    def on_event(self, event: dict, state) -> None:
        gq = self.core.gui_queue
        ev = event.get("event")

        match ev:

            case "ColonisationSystemClaim":
                # A new colonisation claim — we learn the system/market before
                # the first depot event.  No resource data yet.
                system    = event.get("StarSystem", "")
                market_id = event.get("MarketID")
                if market_id is not None:
                    self._upsert_site(
                        market_id=market_id,
                        system=system,
                        station="",
                        progress=0.0,
                        complete=False,
                        failed=False,
                        resources={},
                    )
                    self._save()
                    if gq: gq.put(("plugin_refresh", "colonisation"))

            case "ColonisationConstructionDepot":
                market_id = event.get("MarketID")
                system    = state.pilot_system or ""
                station_raw = state.pilot_body or ""
                if not station_raw:
                    station_raw = event.get("StationName", "")
                station   = _short_station_name(station_raw, system)
                progress  = float(event.get("ConstructionProgress", 0.0))
                complete  = bool(event.get("ConstructionComplete", False))
                failed    = bool(event.get("ConstructionFailed", False))

                resources: dict[str, dict] = {}
                for r in event.get("ResourcesRequired", []):
                    name_raw  = r.get("Name_Localised") or r.get("Name", "")
                    key       = _canon(r.get("Name", name_raw))
                    required  = int(r.get("RequiredAmount", 0))
                    provided  = int(r.get("ProvidedAmount", 0))
                    resources[key] = {
                        "name":     name_raw.strip(),
                        "required": required,
                        "provided": provided,
                    }

                if market_id is not None:
                    self._upsert_site(market_id, system, station,
                                      progress, complete, failed, resources)
                    state._colonisation_current_market_id = market_id
                    state.colonisation_docked = True
                    self._save()
                    if gq: gq.put(("plugin_refresh", "colonisation"))

            case "ColonisationContribution":
                market_id = event.get("MarketID")
                site      = self._find_site(market_id)
                if site is None:
                    return
                for contrib in event.get("Contributions", []):
                    name_raw = contrib.get("Name_Localised") or contrib.get("Name", "")
                    key      = _canon(contrib.get("Name", name_raw))
                    amount   = int(contrib.get("Amount", 0))
                    if key in site["resources"]:
                        site["resources"][key]["provided"] = min(
                            site["resources"][key]["provided"] + amount,
                            site["resources"][key]["required"],
                        )
                    else:
                        # Resource not in depot manifest yet — add as delivered
                        site["resources"][key] = {
                            "name":     name_raw.strip(),
                            "required": amount,
                            "provided": amount,
                        }
                self._save()
                if gq: gq.put(("plugin_refresh", "colonisation"))

            case "ColonisationConstructionComplete":
                market_id = event.get("MarketID")
                site      = self._find_site(market_id)
                if site is not None:
                    site["complete"]  = True
                    site["progress"]  = 1.0
                    self._save()
                    if gq: gq.put(("plugin_refresh", "colonisation"))

            case "ColonisationConstructionFailed":
                market_id = event.get("MarketID")
                site      = self._find_site(market_id)
                if site is not None:
                    site["failed"] = True
                    self._save()
                    if gq: gq.put(("plugin_refresh", "colonisation"))

            case "Docked":
                market_id = event.get("MarketID")
                site      = self._find_site(market_id) if market_id else None
                if site:
                    state._colonisation_current_market_id = market_id
                    state.colonisation_docked = True
                else:
                    state.colonisation_docked = False
                    state._colonisation_current_market_id = None
                if gq: gq.put(("plugin_refresh", "colonisation"))

            case "Undocked" | "Location":
                state.colonisation_docked = False
                state._colonisation_current_market_id = None
                if gq: gq.put(("plugin_refresh", "colonisation"))

    def get_summary_line(self) -> str | None:
        """Return a one-line summary for periodic Discord/terminal output."""
        sites = self.core.state.colonisation_sites
        active = [s for s in sites if not s.get("complete") and not s.get("failed")]
        if not active:
            return None
        parts = []
        for s in active:
            pct = round(s.get("progress", 0.0) * 100)
            remaining = sum(
                max(0, r["required"] - r["provided"])
                for r in s.get("resources", {}).values()
            )
            parts.append(f"{s['station'] or s['system']}: {pct}% ({remaining:,} t remaining)")
        return "- Colonisation: " + " | ".join(parts)
