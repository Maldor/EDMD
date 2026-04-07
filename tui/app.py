"""
tui/app.py — Textual TUI application for EDMD.

Three-column layout matching the default dashboard arrangement:
  Left   : Career  |  Session Stats  |  Colonisation
  Centre : Commander  |  Alerts  |  Mission Stack  |  Cargo
  Right  : Crew/SLF  |  Assets  |  Engineering

Hotkeys
  q       Quit
  r       Reset session
  c       Clear alerts
  ctrl+o  Options (theme picker)
"""
from __future__ import annotations
import queue
from pathlib import Path
from typing  import TYPE_CHECKING

from textual.app       import App, ComposeResult
from textual.binding   import Binding
from textual.widgets    import Header, Footer
from textual.containers import Horizontal, Vertical, VerticalScroll

from tui.preferences   import PreferencesScreen
from tui.reports       import ReportsScreen
from tui.blocks.career import CareerBlock
from tui.blocks.session_stats import SessionStatsBlock
from tui.blocks.colonisation  import ColonisationBlock
from tui.blocks.commander     import CommanderBlock
from tui.blocks.alerts        import AlertsBlock
from tui.blocks.missions      import MissionsBlock
from tui.blocks.cargo         import CargoBlock
from tui.blocks.crew_slf      import CrewSlfBlock
from tui.blocks.assets        import AssetsBlock
from tui.blocks.engineering   import EngineeringBlock
from tui.theme import build_css

if TYPE_CHECKING:
    from core.core_api import CoreAPI

# ── Event → block-id dispatch table ──────────────────────────────────────────

_MSG_DISPATCH: dict[str, list[str]] = {
    "career_update":      ["block-career"],
    "stats_update":       ["block-stats"],
    "colonisation_update":["block-colon"],
    "crew_update":        ["block-crew"],
    "slf_update":         ["block-crew"],
    "vessel_update":      ["block-commander"],
    "location_update":    ["block-commander"],
    "mission_update":     ["block-missions"],
    "cargo_update":       ["block-cargo"],
    "assets_update":      ["block-assets"],
    "materials_update":   ["block-eng"],
    "alert_update":       ["block-alerts"],
    "pp_update":          ["block-career", "block-commander"],
    "cmdr_update":        ["block-commander"],
    "capi_updated":       ["block-commander", "block-crew", "block-assets", "block-cargo"],
}

_PLUGIN_TO_BLOCK: dict[str, str] = {
    "career":        "block-career",
    "session_stats": "block-stats",
    "colonisation":  "block-colon",
    "crew_slf":      "block-crew",
    "commander":     "block-commander",
    "missions":      "block-missions",
    "cargo":         "block-cargo",
    "assets":        "block-assets",
    "engineering":   "block-eng",
    "alerts":        "block-alerts",
}



# ── Main app ──────────────────────────────────────────────────────────────────

class EdmdTui(App):
    """EDMD Textual dashboard."""

    BINDINGS = [
        Binding("ctrl+q", "quit",          "Quit"),
        Binding("ctrl+r", "reset_session", "Reset Session"),
        Binding("ctrl+l", "clear_alerts",  "Clear Alerts"),
        Binding("r",      "reports",       "Reports"),
        Binding("ctrl+o", "options",       "Options"),
    ]

    def __init__(self, core: "CoreAPI", program: str, version: str,
                 theme: str = "default") -> None:
        super().__init__()
        self._core    = core
        self._program = program
        self._version = version
        self._theme   = theme
        self.CSS      = build_css(theme)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="dashboard"):
            with Vertical(id="col-left"):
                yield CareerBlock(self._core,       id="block-career")
                yield SessionStatsBlock(self._core, id="block-stats")
                yield ColonisationBlock(self._core, id="block-colon")
            with Vertical(id="col-centre"):
                yield CommanderBlock(self._core,    id="block-commander")
                yield AlertsBlock(self._core,       id="block-alerts")
                yield MissionsBlock(self._core,     id="block-missions")
                yield CargoBlock(self._core,        id="block-cargo")
            with Vertical(id="col-right"):
                yield CrewSlfBlock(self._core,      id="block-crew")
                yield AssetsBlock(self._core,       id="block-assets")
                yield EngineeringBlock(self._core,  id="block-eng")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"{self._program}  v{self._version}"
        self._refresh_all()
        self.set_interval(0.25, self._poll_queue)

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        dirty: set[str] = set()
        try:
            while True:
                msg_type, payload = self._core.gui_queue.get_nowait()
                targets = _MSG_DISPATCH.get(msg_type)
                if targets is None:
                    if msg_type == "plugin_refresh" and isinstance(payload, str):
                        bid = _PLUGIN_TO_BLOCK.get(payload)
                        if bid:
                            dirty.add(bid)
                        else:
                            dirty.update(self._all_block_ids())
                    else:
                        dirty.update(self._all_block_ids())
                else:
                    dirty.update(targets)
        except queue.Empty:
            pass
        for bid in dirty:
            self._refresh_block(bid)

    def _refresh_block(self, block_id: str) -> None:
        try:
            block = self.query_one(f"#{block_id}")
            if hasattr(block, "refresh_data"):
                block.refresh_data()
        except Exception:
            pass

    def _refresh_all(self) -> None:
        for bid in self._all_block_ids():
            self._refresh_block(bid)

    def _all_block_ids(self) -> list[str]:
        return [
            "block-career", "block-stats", "block-colon",
            "block-commander", "block-alerts", "block-missions", "block-cargo",
            "block-crew", "block-assets", "block-eng",
        ]

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_quit(self) -> None:
        self.exit()

    def action_reset_session(self) -> None:
        self._core.plugin_call("session_stats", "on_new_session", 0)

    def action_clear_alerts(self) -> None:
        self._core.plugin_call("alerts", "clear_alerts")

    def action_reports(self) -> None:
        self.push_screen(ReportsScreen(self._core))

    def action_options(self) -> None:
        self.push_screen(PreferencesScreen(self._core))


def run_tui(core: "CoreAPI", program: str, version: str, theme: str = "default") -> None:
    """Entry point: build and run the Textual app synchronously."""
    app = EdmdTui(core, program, version, theme=theme)
    app.run()
