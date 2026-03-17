"""
builtins/mode/plugin.py — Activity mode tracking and no-kill timeout.

Maintains state.active_mode (one of the MODE_* constants below).
Mode is purely advisory — other plugins and blocks read it to adjust
their behaviour.  Nothing is forced.

No-kill timeout (Combat mode only)
------------------------------------
When mode == MODE_COMBAT, the plugin monitors time since last kill.
If QuitOnNoKillsMinutes (from config profile) is set and non-zero, and
the player has been in-game with no kills for that many minutes, the
session management plugin is notified to flush.

Quit-to-menu pause
-------------------
Kill monitoring pauses whenever state.in_game is False (Music:MainMenu
or Shutdown journal events set this via the commander plugin).  The
no-kill timer resets when the player re-enters the game.

State written to MonitorState:
    active_mode   str   — one of the MODE_* constants, default MODE_NONE

GUI block: col=8, row=6, width=8, height=4
"""

import time

from core.plugin_loader import BasePlugin

# Mode constants — readable strings used as display labels
MODE_NONE        = "None"
MODE_COMBAT      = "Combat"
MODE_MINING      = "Mining"
MODE_CZ          = "Combat Zone"
MODE_XBIO        = "Exobiology"
MODE_COLONIZE    = "Colonization"

ALL_MODES = [MODE_NONE, MODE_COMBAT, MODE_MINING, MODE_CZ, MODE_XBIO, MODE_COLONIZE]

CFG_DEFAULTS = {
    "QuitOnNoKillsMinutes": 0,     # 0 = disabled
}


class ModePlugin(BasePlugin):
    PLUGIN_NAME    = "mode"
    PLUGIN_DISPLAY = "Mode"
    PLUGIN_VERSION = "1.0.0"

    DEFAULT_COL    = 8
    DEFAULT_ROW    = 6
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 4

    SUBSCRIBED_EVENTS = [
        "Bounty", "FactionKillBond",    # kills — reset no-kill timer
        "LoadGame",                      # new session — reset timer
        "Music",                         # MainMenu track — pause monitoring
        "Shutdown",                      # quit to desktop — pause monitoring
    ]

    def on_load(self, core) -> None:
        super().on_load(core)
        s = core.state
        if not hasattr(s, "active_mode"):
            s.active_mode = MODE_COMBAT  # default — combat monitoring active from start

        self._last_kill_mono: float = 0.0   # monotonic time of last kill
        self._alerted:        bool  = False  # prevent repeated flush calls

    def on_event(self, event: dict, state) -> None:
        ev = event.get("event")
        gq = self.core.gui_queue

        if ev in ("Bounty", "FactionKillBond"):
            self._last_kill_mono = time.monotonic()
            self._alerted        = False
            if gq: gq.put(("plugin_refresh", "mode"))

        elif ev == "LoadGame":
            self._last_kill_mono = 0.0
            self._alerted        = False
            if gq: gq.put(("plugin_refresh", "mode"))

        elif ev == "Music" and event.get("MusicTrack") == "MainMenu":
            # Pause — don't reset timer, just stop counting until in_game again
            if gq: gq.put(("plugin_refresh", "mode"))

        elif ev == "Shutdown":
            if gq: gq.put(("plugin_refresh", "mode"))

    def tick(self, state) -> None:
        """Called every second by the GUI tick.  Check no-kill timeout."""
        if state.active_mode != MODE_COMBAT:
            return
        if not state.in_game:
            return
        if self._alerted:
            return

        cfg           = self.core.cfg
        limit_minutes = cfg.pcfg("QuitOnNoKillsMinutes", 0)
        if not limit_minutes:
            return

        # No kills yet this session — only start counting after first kill
        if self._last_kill_mono == 0.0:
            return

        elapsed_minutes = (time.monotonic() - self._last_kill_mono) / 60
        if elapsed_minutes >= limit_minutes:
            self._alerted = True
            # Notify any registered session management plugin
            try:
                self.core.plugin_call(
                    "session_manager", "flush_session",
                    f"No kills for {elapsed_minutes:.0f} min (threshold {limit_minutes} min)"
                )
            except Exception:
                pass

    def set_mode(self, mode: str) -> None:
        """Set active mode — called from the GUI block."""
        if mode not in ALL_MODES:
            return
        self.core.state.active_mode = mode
        self._last_kill_mono = 0.0
        self._alerted        = False
        gq = self.core.gui_queue
        if gq: gq.put(("plugin_refresh", "mode"))

