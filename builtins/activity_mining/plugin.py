"""
builtins/activity_mining/plugin.py — Mining session tracking.

Tracks prospected asteroids, refined tonnage, and limpet efficiency.
Income from selling mined cargo is tracked by activity_trade.

Tab title: Mining
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin


class ActivityMiningPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_mining"
    PLUGIN_DISPLAY      = "Mining Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks asteroid prospecting and ore refined."
    ACTIVITY_TAB_TITLE  = "Mining"

    SUBSCRIBED_EVENTS = [
        "MiningRefined",
        "ProspectedAsteroid",
        "LaunchDrone",         # limpet usage
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.tonnes_refined:   float = 0.0
        self.asteroids_prospected: int = 0
        self.limpets_used:     int   = 0
        self.material_tally:   dict  = {}  # material_name → tonnes
        self.session_start_time = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")

        match ev:

            case "MiningRefined":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                material = (
                    event.get("Type_Localised") or event.get("Type", "Unknown")
                ).strip()
                self.tonnes_refined += 1
                self.material_tally[material] = (
                    self.material_tally.get(material, 0) + 1
                )
                gq = self.core.gui_queue
                if gq: gq.put(("stats_update", None))

            case "ProspectedAsteroid":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.asteroids_prospected += 1

            case "LaunchDrone" if event.get("Type") == "Collection":
                self.limpets_used += 1

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.tonnes_refined > 0 or self.asteroids_prospected > 0

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.tonnes_refined > 0:
            rows.append({
                "label": "Tonnes refined",
                "value": f"{self.tonnes_refined:.0f} t",
                "rate":  None,
            })
        if self.asteroids_prospected > 0 and self.tonnes_refined > 0:
            efficiency = self.tonnes_refined / max(1, self.asteroids_prospected)
            rows.append({
                "label": "Asteroids prospected",
                "value": str(self.asteroids_prospected),
                "rate":  f"{efficiency:.1f} t/ast",
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.limpets_used > 0:
            rows.append({
                "label": "Collection limpets",
                "value": str(self.limpets_used),
                "rate":  None,
            })
        if self.material_tally:
            rows.append({"label": "─── Materials ───", "value": "", "rate": None})
            for mat, count in sorted(
                self.material_tally.items(), key=lambda x: -x[1]
            ):
                rows.append({"label": f"  {mat}", "value": f"{count} t", "rate": None})
        return rows
