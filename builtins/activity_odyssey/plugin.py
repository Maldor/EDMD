"""
builtins/activity_odyssey/plugin.py — Odyssey on-foot session tracking.

Tracks on-foot kills, settlements raided, and credits from Odyssey activities.
Tab title: Odyssey
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits


class ActivityOdysseyPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_odyssey"
    PLUGIN_DISPLAY      = "Odyssey Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks on-foot combat and Odyssey activities."
    ACTIVITY_TAB_TITLE  = "Odyssey"

    SUBSCRIBED_EVENTS = [
        "SuitLoadout",          # on-foot session detection
        "BookDropship",         # settlement approach
        "Disembark",            # leaving ship on foot
        "Embark",               # returning to ship
        "ShootPedestrian",      # deprecated but some older journals have it
    ]

    # Frontier does not currently emit a dedicated on-foot kill event.
    # Best available proxy: FighterDestroyed (ship kills), but for on-foot
    # kills we watch for combat-related RPC events.
    # This plugin will expand as Frontier exposes richer Odyssey journal data.

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.disembark_count:   int  = 0
        self.session_start_time = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")

        match ev:

            case "Disembark":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.disembark_count += 1

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.disembark_count > 0

    def get_summary_rows(self) -> list[dict]:
        rows = []
        if self.disembark_count > 0:
            rows.append({
                "label": "On-foot deployments",
                "value": str(self.disembark_count),
                "rate":  None,
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        return self.get_summary_rows()
