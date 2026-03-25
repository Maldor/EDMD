"""
builtins/activity_odyssey/plugin.py — Odyssey on-foot session tracking.

Tracks meaningful Odyssey activities: planet surface deployments, settlement
approaches (categorised by type), guardian site visits, engineer visits,
and combat bonds redeemed.

ApproachSettlement fires for three distinct location categories:
  - Engineer bases  (StationGovernment contains "$government_engineer")
  - Guardian structures (Name starts with "$Ancient_")
  - Regular settlements and installations

Tab title: Odyssey
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits


def _is_engineer(station_gov: str) -> bool:
    return "$government_engineer" in station_gov.lower()


def _is_guardian(name: str) -> bool:
    return name.startswith("$Ancient_")


class ActivityOdysseyPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME        = "activity_odyssey"
    PLUGIN_DISPLAY     = "Odyssey Activity"
    PLUGIN_VERSION     = "1.1.0"
    PLUGIN_DESCRIPTION = "Tracks on-foot deployments, settlements, and Odyssey activities."
    ACTIVITY_TAB_TITLE = "Odyssey"

    SUBSCRIBED_EVENTS = [
        "Disembark",
        "ApproachSettlement",
        "RedeemVoucher",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.surface_deployments: int = 0   # Disembark on planet, not taxi/SRV
        self.settlements_visited: int = 0   # ApproachSettlement, non-engineer, non-guardian
        self.engineer_visits:     int = 0   # ApproachSettlement, government=engineer
        self.guardian_sites:      int = 0   # ApproachSettlement, $Ancient_*
        self.combat_bonds:        int = 0   # RedeemVoucher Type=CombatBond credits
        self.session_start_time       = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")
        gq      = self.core.gui_queue

        match ev:

            case "Disembark":
                if event.get("OnPlanet") and not event.get("Taxi") and not event.get("SRV"):
                    if self.session_start_time is None:
                        self.session_start_time = logtime
                    self.surface_deployments += 1
                    if gq:
                        gq.put(("stats_update", None))

            case "ApproachSettlement":
                name = event.get("Name", "")
                gov  = event.get("StationGovernment", "")
                if self.session_start_time is None:
                    self.session_start_time = logtime
                if _is_guardian(name):
                    self.guardian_sites += 1
                elif _is_engineer(gov):
                    self.engineer_visits += 1
                else:
                    self.settlements_visited += 1
                if gq:
                    gq.put(("stats_update", None))

            case "RedeemVoucher":
                if event.get("Type") == "CombatBond":
                    self.combat_bonds += event.get("Amount", 0)
                    if gq:
                        gq.put(("stats_update", None))

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return (
            self.surface_deployments > 0
            or self.settlements_visited > 0
            or self.engineer_visits > 0
            or self.guardian_sites > 0
            or self.combat_bonds > 0
        )

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.surface_deployments > 0:
            rows.append({"label": "Surface deployments", "value": str(self.surface_deployments), "rate": None})
        if self.settlements_visited > 0:
            rows.append({"label": "Settlements",         "value": str(self.settlements_visited), "rate": None})
        if self.combat_bonds > 0:
            rows.append({"label": "Combat bonds",        "value": fmt_credits(self.combat_bonds), "rate": None})
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.engineer_visits > 0:
            rows.append({"label": "Engineer visits", "value": str(self.engineer_visits), "rate": None})
        if self.guardian_sites > 0:
            rows.append({"label": "Guardian sites",  "value": str(self.guardian_sites),  "rate": None})
        return rows
