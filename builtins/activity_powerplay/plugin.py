"""
builtins/activity_powerplay/plugin.py — PowerPlay session tracking.

Tracks merits earned across all PowerPlay activities — not just kills.
PowerplayMerits fires for bounties, trade, missions, and other PP actions.

Removes merit tracking from session_stats, which previously coupled merits
to kill events via a pending_merit_events counter (a fragile correlation).

Tab title: PowerPlay
"""

from core.plugin_loader import BasePlugin
from core.activity import ActivityProviderMixin
from core.emit import Terminal, rate_per_hour


class ActivityPowerplayPlugin(BasePlugin, ActivityProviderMixin):
    PLUGIN_NAME         = "activity_powerplay"
    PLUGIN_DISPLAY      = "PowerPlay Activity"
    PLUGIN_VERSION      = "1.0.0"
    PLUGIN_DESCRIPTION  = "Tracks PowerPlay merits and rank progress."
    ACTIVITY_TAB_TITLE  = "PowerPlay"

    SUBSCRIBED_EVENTS = [
        "Powerplay",             # on-login: current power, rank, total merits
        "PowerplayMerits",       # merits earned (any activity)
        "PowerplayRank",         # rank change
        "PowerplayJoin",
        "PowerplayLeave",
        "PowerplayDefect",
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_session_provider(self)
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.merits_earned:    int  = 0   # gained this session
        self.rank_start:       int | None = None
        self.rank_current:     int | None = None
        self.power:            str | None = None
        self.session_start_time = None

    def on_session_reset(self) -> None:
        # Preserve power/rank context across session gap — only reset counters
        self.merits_earned    = 0
        self.rank_start       = self.rank_current
        self.session_start_time = None

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")
        gq      = self.core.gui_queue

        match ev:

            case "Powerplay":
                self.power        = event.get("Power")
                self.rank_current = event.get("Rank")
                if self.rank_start is None:
                    self.rank_start = self.rank_current
                # Sync to state for commander block
                state.pp_power        = self.power
                state.pp_rank         = self.rank_current
                state.pp_merits_total = event.get("Merits")

            case "PowerplayMerits":
                gained = event.get("MeritsGained", 0)
                if gained > 0:
                    if self.session_start_time is None:
                        self.session_start_time = logtime
                    self.merits_earned += gained
                    # Keep state in sync for commander block
                    total = event.get("TotalMerits")
                    if total is not None:
                        state.pp_merits_total = total
                    core = self.core
                    core.emitter.emit(
                        msg_term=(
                            f"Merits: +{gained:,}"
                            + (f" ({self.power})" if self.power else "")
                        ),
                        emoji="⭐", sigil="+  MERC",
                        timestamp=logtime,
                        loglevel=self.core.notify_levels.get("MeritEvent", 0),
                    )
                    if gq: gq.put(("stats_update", None))

            case "PowerplayRank":
                self.rank_current    = event.get("Rank")
                state.pp_rank        = self.rank_current
                if gq: gq.put(("stats_update", None))

            case "PowerplayJoin":
                self.power        = event.get("Power")
                self.rank_current = 1
                self.rank_start   = 1
                state.pp_power    = self.power
                state.pp_rank     = 1

            case "PowerplayLeave" | "PowerplayDefect":
                self.power = event.get("Power") if ev == "PowerplayDefect" else None
                state.pp_power = self.power
                state.pp_rank  = None

    # ── ActivityProviderMixin ─────────────────────────────────────────────────

    def has_activity(self) -> bool:
        return self.merits_earned > 0

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
        if self.merits_earned > 0:
            rate = (f"{rate_per_hour(dur / self.merits_earned, 1)} /hr"
                    if dur else "—")
            rows.append({
                "label": "Merits",
                "value": f"{self.merits_earned:,}",
                "rate":  rate,
            })
        return rows

    def get_tab_rows(self) -> list[dict]:
        rows = self.get_summary_rows()
        if self.power:
            rows.append({"label": "Power", "value": self.power, "rate": None})
        if self.rank_current is not None:
            rank_str = str(self.rank_current)
            if self.rank_start is not None and self.rank_current != self.rank_start:
                rank_str += f" (was {self.rank_start})"
            rows.append({"label": "Rank", "value": rank_str, "rate": None})
        return rows
