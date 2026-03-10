"""
gui/blocks/session_stats.py — Kill, credit, merit, and duration stats block.

Mirrors _build_stats_panel / _refresh_stats from the original edmd_gui.py.
Column-aligned total | rate /hr display for all three stat rows.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget


class SessionStatsBlock(BlockWidget):
    BLOCK_TITLE = "Session Stats"
    BLOCK_CSS   = "stats-block"

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)
        scroll_body = self._make_scroll_body(body)

        # Duration on its own row
        row, self._stat_duration = self.make_row("Duration")
        scroll_body.append(row)

        # Three stat rows — each a monospace label spanning full width,
        # right-aligned. _refresh formats them with padded columns so the
        # pipe delimiters align across all three rows.
        for key_text, attr in [
            ("Kills",    "_stat_line_kills"),
            ("Bounties", "_stat_line_credits"),
            ("Merits",   "_stat_line_merits"),
        ]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row.add_css_class("data-row")
            key = self.make_label(key_text, css_class="data-key")
            key.set_hexpand(False)
            row.append(key)
            lbl = Gtk.Label(label="—")
            lbl.add_css_class("stat-line")
            lbl.set_hexpand(True)
            lbl.set_xalign(1.0)
            row.append(lbl)
            setattr(self, attr, lbl)
            scroll_body.append(row)

    def refresh(self) -> None:
        s   = self.state
        ses = self.session

        duration = 0.0
        if s.session_start_time and s.event_time:
            duration = (s.event_time - s.session_start_time).total_seconds()

        # Show "—" when no active session (e.g. between jumps), not "0:00"
        self._stat_duration.set_label(
            self.fmt_duration(duration) if duration > 0 else "—"
        )

        # Compute raw totals and rates
        kills_total = str(ses.kills)
        if ses.kills > 0 and duration > 0:
            kills_rate = str(self.rate_per_hour(duration / ses.kills, 1))
        else:
            kills_rate = "—"

        cred_total = self.fmt_credits(ses.credit_total)
        if ses.credit_total > 0 and duration > 0:
            cred_rate = self.fmt_credits(self.rate_per_hour(duration / ses.credit_total, 2))
        else:
            cred_rate = "—"

        merit_total = str(ses.merits)
        if ses.merits > 0 and duration > 0:
            merit_rate = str(self.rate_per_hour(duration / ses.merits, 1))
        else:
            merit_rate = "—"

        # Align columns: pad totals so pipe is at same position, pad rates
        # so /hr suffix aligns too — preserves exact original formatting.
        totals = [kills_total, cred_total, merit_total]
        rates  = [kills_rate,  cred_rate,  merit_rate]
        tw = max(len(t) for t in totals)
        rw = max(len(r) for r in rates)

        def _fmt(total, rate):
            return f"{total:>{tw}}  |  {rate:>{rw}} /hr"

        self._stat_line_kills.set_label(  _fmt(kills_total,  kills_rate))
        self._stat_line_credits.set_label(_fmt(cred_total,   cred_rate))
        self._stat_line_merits.set_label( _fmt(merit_total,  merit_rate))
