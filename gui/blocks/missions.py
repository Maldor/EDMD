"""
gui/blocks/missions.py — Mission stack block.

Mirrors _build_mission_panel / _refresh_missions from the original edmd_gui.py.
Shows stack value, completion progress, and per-faction kill rows.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget


class MissionsBlock(BlockWidget):
    BLOCK_TITLE = "Mission Stack"
    BLOCK_CSS   = "missions-block"

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)

        # Stack value row
        row, self._miss_value = self.make_row("Stack Value")
        body.append(row)

        # Progress row — key label changes between "Completed" / "Complete"
        row_p = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row_p.add_css_class("data-row")
        self._miss_progress_key = self.make_label("Completed", css_class="data-key")
        self._miss_progress_key.set_hexpand(False)
        row_p.append(self._miss_progress_key)
        self._miss_progress = self.make_label("—", css_class="data-value")
        self._miss_progress.set_hexpand(True)
        self._miss_progress.set_xalign(1.0)
        row_p.append(self._miss_progress)
        body.append(row_p)



    def refresh(self) -> None:
        s = self.state

        if s.stack_value > 0:
            total = len(s.active_missions)
            done  = s.missions_complete
            rem   = total - done

            self._miss_value.set_label(self.fmt_credits(s.stack_value))

            if rem == 0:
                self._miss_progress_key.set_label("Complete")
                self._miss_progress.set_label(f"{done}/{total}")
                self._miss_progress.remove_css_class("status-active")
                self._miss_progress.add_css_class("status-ready")
                self._miss_progress_key.remove_css_class("status-active")
                self._miss_progress_key.add_css_class("status-ready")
            else:
                self._miss_progress_key.set_label("Completed")
                self._miss_progress.set_label(f"{done}/{total}")
                self._miss_progress.remove_css_class("status-ready")
                self._miss_progress.add_css_class("status-active")
                self._miss_progress_key.remove_css_class("status-ready")
                self._miss_progress_key.add_css_class("status-active")


        else:
            for w in [self._miss_value, self._miss_progress]:
                w.set_label("—")
            self._miss_progress_key.set_label("Completed")
            for w in [self._miss_progress, self._miss_progress_key]:
                w.remove_css_class("status-ready")
                w.remove_css_class("status-active")
