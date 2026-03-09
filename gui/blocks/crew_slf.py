"""
gui/blocks/crew_slf.py — NPC Crew and SLF status block.

Mirrors _build_crew_panel / _refresh_crew from the original edmd_gui.py exactly.
Hidden when no active crew.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget
from gui.helpers    import hull_css, fmt_crew_active, PP_RANK_NAMES
from datetime       import datetime, timezone


class CrewSlfBlock(BlockWidget):
    BLOCK_TITLE = "CREW"
    BLOCK_CSS   = "crew-block"

    def build(self, parent: Gtk.Box) -> None:
        # ── Header: crew name (left) + SLF type (right) ───────────────────────
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._crew_header_lbl = Gtk.Label(label="CREW")
        self._crew_header_lbl.set_xalign(0.0)
        self._crew_header_lbl.set_hexpand(True)
        hdr_box.append(self._crew_header_lbl)
        self._crew_slf_type_hdr = Gtk.Label(label="")
        self._crew_slf_type_hdr.set_xalign(1.0)
        hdr_box.append(self._crew_slf_type_hdr)

        body = self._build_section(parent, title_widget=hdr_box)

        for lbl_text, attr in [
            ("Rank",   "_crew_rank_lbl"),
            ("Hired",  "_crew_hired_lbl"),
            ("Active", "_crew_active_lbl"),
            ("Paid",   "_crew_paid_lbl"),
            ("SLF",    "_crew_slf_status"),
        ]:
            row, val = self.make_row(lbl_text)
            setattr(self, attr, val)
            body.append(row)

        # Hidden by default until crew is active
        self.set_visible(False)

    def refresh(self) -> None:
        s         = self.state
        has_crew  = bool(s.crew_name) and s.crew_active
        self.set_visible(has_crew)
        if not has_crew:
            return

        # ── Header ────────────────────────────────────────────────────────────
        if s.cmdr_in_slf:
            self._crew_header_lbl.set_label(
                f"CREW: {s.crew_name or 'NPC'}  [Flying {s.pilot_ship or 'Ship'}]"
            )
        else:
            self._crew_header_lbl.set_label(f"CREW: {s.crew_name or 'NPC'}")
        self._crew_slf_type_hdr.set_label(s.slf_type or "")

        # ── Rank ──────────────────────────────────────────────────────────────
        rank_str = (
            PP_RANK_NAMES[s.crew_rank]
            if s.crew_rank is not None and 0 <= s.crew_rank < len(PP_RANK_NAMES)
            else "—"
        )
        self._crew_rank_lbl.set_label(rank_str)

        # ── Hired ─────────────────────────────────────────────────────────────
        self._crew_hired_lbl.set_label(
            s.crew_hire_time.strftime("%d %b %Y") if s.crew_hire_time else "Unknown"
        )

        # ── Active duration ───────────────────────────────────────────────────
        if s.crew_hire_time:
            self._crew_active_lbl.set_label(
                fmt_crew_active(datetime.now(timezone.utc) - s.crew_hire_time)
            )
        else:
            self._crew_active_lbl.set_label("—")

        # ── Total paid ────────────────────────────────────────────────────────
        if s.crew_total_paid is not None and s.crew_total_paid > 0:
            prefix = "" if s.crew_paid_complete else "≥ "
            self._crew_paid_lbl.set_label(
                f"{prefix}{self.fmt_credits(s.crew_total_paid)}"
            )
        else:
            self._crew_paid_lbl.set_label("—")

        # ── SLF status (hidden when no bay fitted) ────────────────────────────
        has_bay = s.has_fighter_bay
        self._crew_slf_status.get_parent().set_visible(has_bay)
        if not has_bay:
            return

        for cls in ("health-good", "health-warn", "health-crit"):
            self._crew_slf_status.remove_css_class(cls)

        all_spent = (
            s.slf_stock_total > 0
            and s.slf_destroyed_count >= s.slf_stock_total
            and not s.slf_docked
            and not s.slf_deployed
        )

        if s.cmdr_in_slf:
            hull_str = f"{s.slf_hull}%" if s.slf_hull is not None else "—"
            self._crew_slf_status.set_label(f"CMDR Aboard  |  Hull {hull_str}")
            self._crew_slf_status.add_css_class(
                hull_css(s.slf_hull) if s.slf_hull is not None else "health-good"
            )
        elif s.slf_docked:
            self._crew_slf_status.set_label("SLF Docked")
            self._crew_slf_status.add_css_class("health-good")
        elif s.slf_deployed:
            hull_str = f"Hull {s.slf_hull}%" if s.slf_hull is not None else "Hull —"
            self._crew_slf_status.set_label(hull_str)
            self._crew_slf_status.add_css_class(
                hull_css(s.slf_hull) if s.slf_hull is not None else "health-good"
            )
        elif all_spent:
            self._crew_slf_status.set_label("All Spent")
            self._crew_slf_status.add_css_class("health-crit")
        else:
            self._crew_slf_status.set_label("Destroyed")
            self._crew_slf_status.add_css_class("health-crit")
