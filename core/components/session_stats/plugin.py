"""
builtins/session_stats/plugin.py — Session timing and summary aggregator.

Owns the session clock and on_new_session boundary logic.
Collects summary rows from registered ActivityProviderMixin plugins.
No longer owns kill/merit/credit counters — those live in activity plugins.

GUI block: col=8, row=0, width=8, height=10 (expanded for tabs).
"""

from core.plugin_loader import BasePlugin
from core.emit import fmt_duration


class SessionStatsPlugin(BasePlugin):
    PLUGIN_NAME    = "session_stats"
    PLUGIN_DISPLAY = "Session Stats"
    PLUGIN_DESCRIPTION = "Session summary and per-activity statistics. Aggregates data from activity plugins."
    PLUGIN_VERSION = "2.0.0"

    SUBSCRIBED_EVENTS = [
        "LoadGame",
        "Shutdown",
    ]

    DEFAULT_COL    = 8
    DEFAULT_ROW    = 0
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 10

    def on_load(self, core) -> None:
        super().on_load(core)
        core.register_block(self, priority=20)
        self._session_start_time = None

    def on_new_session(self, gap_minutes: float = 0) -> None:
        """Called by commander plugin when a new session boundary is detected."""
        self._session_start_time = None
        # Notify all registered providers
        for provider in getattr(self.core, "session_providers", []):
            try:
                provider.on_session_reset()
            except Exception:
                pass
        gq = self.core.gui_queue
        if gq: gq.put(("stats_update", None))

    def on_event(self, event: dict, state) -> None:
        ev      = event.get("event")
        logtime = event.get("_logtime")

        if ev == "LoadGame":
            if self._session_start_time is None:
                self._session_start_time = logtime

    def session_duration_seconds(self) -> float:
        """Wall-clock duration of the current session in seconds."""
        if not self._session_start_time:
            return 0.0
        state = self.core.state
        if state.event_time:
            return (state.event_time - self._session_start_time).total_seconds()
        return 0.0
