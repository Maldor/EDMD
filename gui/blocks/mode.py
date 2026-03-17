"""
gui/blocks/mode.py — Activity mode selection block.

Displays five mode buttons: Combat, Mining, CZ, Xbio, Colonization.
Active mode is highlighted.  None clears the selection.
Combat mode shows a live no-kill timer when QuitOnNoKillsMinutes is set.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

import time
from gui.block_base import BlockWidget

try:
    from builtins.mode.plugin import ALL_MODES, MODE_NONE, MODE_COMBAT
except ImportError:
    ALL_MODES  = ["None", "Combat", "Mining", "Combat Zone", "Exobiology", "Colonization"]
    MODE_NONE  = "None"
    MODE_COMBAT = "Combat"


class ModeBlock(BlockWidget):
    BLOCK_TITLE = "Mode"
    BLOCK_CSS   = "mode-block"

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)

        # Mode button grid — 2 columns
        grid = Gtk.Grid()
        grid.set_column_spacing(4)
        grid.set_row_spacing(4)
        grid.set_margin_top(4)
        grid.set_margin_start(4)
        grid.set_margin_end(4)
        body.append(grid)

        self._mode_btns: dict[str, Gtk.Button] = {}

        display_modes = [m for m in ALL_MODES if m != MODE_NONE]
        for i, mode in enumerate(display_modes):
            btn = Gtk.Button(label=mode)
            btn.add_css_class("mode-btn")
            btn.set_hexpand(True)
            btn.connect("clicked", self._on_mode_click, mode)
            grid.attach(btn, i % 2, i // 2, 1, 1)
            self._mode_btns[mode] = btn

        # Clear / None button — full width below grid
        clear_btn = Gtk.Button(label="Clear Mode")
        clear_btn.add_css_class("mode-btn-clear")
        clear_btn.set_margin_top(2)
        clear_btn.set_margin_start(4)
        clear_btn.set_margin_end(4)
        clear_btn.connect("clicked", self._on_mode_click, MODE_NONE)
        body.append(clear_btn)
        self._mode_btns[MODE_NONE] = clear_btn

        # Separator + info row (no-kill timer in combat mode)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        row_info, self._info_lbl = self.make_row("Status")
        body.append(row_info)

    def _on_mode_click(self, _btn, mode: str) -> None:
        self.core.plugin_call("mode", "set_mode", mode)

    def refresh(self) -> None:
        state       = self.state
        active_mode = getattr(state, "active_mode", MODE_NONE)
        in_game     = getattr(state, "in_game", False)

        for mode, btn in self._mode_btns.items():
            if mode == active_mode:
                btn.add_css_class("mode-btn-active")
            else:
                btn.remove_css_class("mode-btn-active")

        # Status row
        if not in_game:
            self._info_lbl.set_label("Not in game")
            return

        if active_mode == MODE_NONE:
            self._info_lbl.set_label("—")
            return

        if active_mode == MODE_COMBAT:
            plugin = self.core._plugins.get("mode")
            lkm    = getattr(plugin, "_last_kill_mono", 0.0) if plugin else 0.0

            cfg           = self.core.cfg
            limit_minutes = cfg.pcfg("QuitOnNoKillsMinutes", 0)

            if lkm == 0.0:
                self._info_lbl.set_label("Waiting for first kill")
            else:
                elapsed = int((time.monotonic() - lkm) / 60)
                if limit_minutes:
                    remaining = max(0, int(limit_minutes - elapsed))
                    self._info_lbl.set_label(f"No kill: {elapsed}m  (quit in {remaining}m)")
                else:
                    self._info_lbl.set_label(f"No kill: {elapsed}m")
        else:
            self._info_lbl.set_label(active_mode)
