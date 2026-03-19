"""
builtins/activity_exploration/plugin.py — Exploration session tracking.

Tracks FSD jumps and distance, FSS/DSS scans, and estimated scan value.
Distance jumped is shown in Summary as it's relevant to all activity types.

Tab title: Exploration
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits


class ActivityExplorationPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_exploration"
    PLUGIN_DISPLAY      = "Exploration Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks jumps, distance, and bodies scanned."
    ACTIVITY_TAB_TITLE  = "Exploration"

    SUBSCRIBED_EVENTS = [
        "FSDJump",
        "Scan",
        "SAAScanComplete",       # DSS probe scan (detailed surface scan)
        "SellExplorationData",   # cartographic data sold
        "MultiSellExplorationData",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.jumps:              int   = 0
        self.distance_ly:        float = 0.0
        self.bodies_fss_scanned: int   = 0   # FSS / auto-scan
        self.bodies_dss_mapped:  int   = 0   # detailed surface scan (probes)
        self.scan_value_est:     int   = 0   # estimated from SellExplorationData
        self.first_discoveries:  int   = 0
        self.session_start_time = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")

        match ev:

            case "FSDJump":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.jumps       += 1
                self.distance_ly += event.get("JumpDist", 0.0)
                gq = self.core.gui_queue
                if gq: gq.put(("stats_update", None))

            case "Scan":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                scan_type = event.get("ScanType", "")
                # Auto-scan and Detailed are FSS/passive; ignore NavBeacon
                if scan_type in ("AutoScan", "Detailed", ""):
                    self.bodies_fss_scanned += 1
                if event.get("WasDiscovered") is False:
                    self.first_discoveries += 1

            case "SAAScanComplete":
                self.bodies_dss_mapped += 1

            case "SellExplorationData" | "MultiSellExplorationData":
                total = event.get("TotalEarnings", 0) or event.get("BaseValue", 0)
                self.scan_value_est += total
                gq = self.core.gui_queue
                if gq: gq.put(("stats_update", None))

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.jumps > 0 or self.bodies_fss_scanned > 0

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.jumps > 0:
            rows.append({
                "label": "Distance jumped",
                "value": f"{self.distance_ly:,.0f} ly",
                "rate":  f"{self.jumps} jumps",
            })
        if self.bodies_fss_scanned > 0:
            rows.append({
                "label": "Bodies scanned",
                "value": str(self.bodies_fss_scanned),
                "rate":  None,
            })
        if self.scan_value_est > 0:
            rows.append({
                "label": "Cartography sold",
                "value": fmt_credits(self.scan_value_est),
                "rate":  None,
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.bodies_dss_mapped > 0:
            rows.append({
                "label": "DSS mapped",
                "value": str(self.bodies_dss_mapped),
                "rate":  None,
            })
        if self.first_discoveries > 0:
            rows.append({
                "label": "First discoveries",
                "value": str(self.first_discoveries),
                "rate":  None,
            })
        return rows
