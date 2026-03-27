"""
builtins/activity_missions/plugin.py — Mission session tracking.

Tracks missions accepted, completed, failed, and credits earned.
Tab title: Missions
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import fmt_credits, rate_per_hour


class ActivityMissionsPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_missions"
    PLUGIN_DISPLAY      = "Missions Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks mission completions and credit rewards."
    ACTIVITY_TAB_TITLE  = "Missions"

    SUBSCRIBED_EVENTS = [
        "MissionAccepted",
        "MissionCompleted",
        "MissionFailed",
        "MissionAbandoned",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.accepted:    int  = 0
        self.completed:   int  = 0
        self.failed:      int  = 0
        self.abandoned:   int  = 0
        self.credits_earned: int = 0
        self.type_tally:  dict = {}  # mission type → count
        self.session_start_time = None

    def on_session_reset(self) -> None:
        self._reset_counters()

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")
        gq      = self.core.gui_queue

        match ev:

            case "MissionAccepted":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.accepted += 1

            case "MissionCompleted":
                if self.session_start_time is None:
                    self.session_start_time = logtime
                self.completed += 1
                reward = event.get("Reward", 0)
                self.credits_earned += reward
                mtype = (
                    event.get("LocalisedName") or
                    event.get("Name", "Unknown")
                ).strip()
                # Normalise: strip trailing _;tag and numbers
                import re as _re
                mtype = _re.sub(r'_\w+$', '', mtype).strip().title()
                self.type_tally[mtype] = self.type_tally.get(mtype, 0) + 1
                if gq: gq.put(("stats_update", None))

            case "MissionFailed":
                self.failed += 1
                if gq: gq.put(("stats_update", None))

            case "MissionAbandoned":
                self.abandoned += 1

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.completed > 0 or self.failed > 0

    def _duration_seconds(self) -> float:
        if not self.session_start_time:
            return 0.0
        state = self.core.state
        if state.event_time:
            return (state.event_time - self.session_start_time).total_seconds()
        return 0.0

    def get_summary_rows(self) -> list[dict]:
        dur  = self._duration_seconds()
        rows = []
        if self.completed > 0:
            cr_rate = (f"{fmt_credits(self.credits_earned)} credits"
                       if self.credits_earned > 0 else None)
            rows.append({
                "label": "Completed",
                "value": str(self.completed),
                "rate":  cr_rate,
            })
        if self.failed > 0:
            rows.append({"label": "Failed", "value": str(self.failed), "rate": None})
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.abandoned > 0:
            rows.append({"label": "Abandoned", "value": str(self.abandoned), "rate": None})
        if self.type_tally:
            rows.append({"label": "─── Mission types ───", "value": "", "rate": None})
            for mtype, count in sorted(
                self.type_tally.items(), key=lambda x: -x[1]
            ):
                rows.append({"label": f"  {mtype}", "value": str(count), "rate": None})
        return rows
