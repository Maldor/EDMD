"""
gui/blocks/career.py — Career and historical statistics block.

Shows cross-session, all-time data sourced from the JournalHistoryPlugin
background scan. Tabs:

  Career     — exploration scanning milestones (bodies, ELWs, first discovers)
  PowerPlay  — total merits and per-system breakdown since current pledge

Data is loaded once the background journal scan completes.  While scanning,
a "Loading…" placeholder is shown.  The block refreshes when it receives
a `career_update` gui_queue message.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget


def _fmt(n: int) -> str:
    return f"{n:,}" if n else "—"


def _fmt_cr(n: int) -> str:
    if not n:
        return "—"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B cr"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M cr"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K cr"
    return f"{n} cr"


class CareerBlock(BlockWidget):
    BLOCK_TITLE = "Career"
    BLOCK_CSS   = "career-block"

    DEFAULT_COL    = 8
    DEFAULT_ROW    = 5
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 6

    _TAB_CAREER    = "Career"
    _TAB_POWERPLAY = "PowerPlay"

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)

        tab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar.add_css_class("mat-tab-bar")
        self._tab_bar.set_hexpand(True)
        tab_row.append(self._tab_bar)
        body.append(tab_row)

        self._stack    = Gtk.Stack()
        self._stack.set_vexpand(True)
        body.append(self._stack)

        self._tab_btns: dict[str, Gtk.Button] = {}
        self._active_tab: str = self._TAB_CAREER

        for title in (self._TAB_CAREER, self._TAB_POWERPLAY):
            self._build_tab(title)
        self._set_active_tab(self._TAB_CAREER)

    def _build_tab(self, title: str) -> Gtk.Box:
        btn = Gtk.Button(label=title)
        btn.add_css_class("mat-tab-btn")
        btn.connect("clicked", lambda _b, t=title: self._set_active_tab(t))
        self._tab_bar.append(btn)
        self._tab_btns[title] = btn

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_end(12)
        scroll  = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("mat-tab-scroll")
        scroll.set_child(content)
        self._stack.add_named(scroll, title)
        return content

    def _set_active_tab(self, title: str) -> None:
        self._active_tab = title
        self._stack.set_visible_child_name(title)
        for t, btn in self._tab_btns.items():
            if t == title:
                btn.add_css_class("mat-tab-active")
            else:
                btn.remove_css_class("mat-tab-active")

    def _get_tab_content(self, title: str) -> Gtk.Box:
        page = self._stack.get_child_by_name(title)
        if page is None:
            return self._build_tab(title)
        vp = page.get_child()
        return vp.get_child() if hasattr(vp, "get_child") else vp

    def _clear_tab(self, title: str) -> Gtk.Box:
        box = self._get_tab_content(title)
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        return box

    def _add_grid_rows(self, grid: Gtk.Grid, rows: list[dict],
                       start: int = 0) -> int:
        i = start
        for r in rows:
            label = r["label"]
            value = r.get("value", "")
            rate  = r.get("rate")

            if not value and not rate:
                sep = Gtk.Label(label=label)
                sep.add_css_class("data-key")
                sep.set_xalign(0.0)
                sep.set_margin_top(4)
                grid.attach(sep, 0, i, 4, 1)
                i += 1
                continue

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("data-key")
            lbl.set_xalign(0.0)
            lbl.set_hexpand(True)
            grid.attach(lbl, 0, i, 1, 1)

            if rate:
                val_lbl = Gtk.Label(label=value)
                val_lbl.add_css_class("data-value")
                val_lbl.set_xalign(1.0)
                grid.attach(val_lbl, 1, i, 1, 1)
                pipe = Gtk.Label(label="|")
                pipe.add_css_class("data-key")
                pipe.set_xalign(0.5)
                grid.attach(pipe, 2, i, 1, 1)
                rate_lbl = Gtk.Label(label=rate)
                rate_lbl.add_css_class("stat-line")
                rate_lbl.set_xalign(1.0)
                grid.attach(rate_lbl, 3, i, 1, 1)
            else:
                val_lbl = Gtk.Label(label=value)
                val_lbl.add_css_class("data-value")
                val_lbl.set_xalign(1.0)
                grid.attach(val_lbl, 1, i, 3, 1)
            i += 1
        return i

    def _make_grid(self) -> Gtk.Grid:
        g = Gtk.Grid()
        g.set_column_spacing(4)
        g.set_row_spacing(1)
        g.add_css_class("stats-grid")
        return g

    def _loading_label(self, box: Gtk.Box) -> None:
        lbl = self.make_label("Scanning journals…", css_class="data-value")
        box.append(lbl)

    def refresh(self) -> None:
        hist = self.core._plugins.get("journal_history")

        for title in (self._TAB_CAREER, self._TAB_POWERPLAY):
            box = self._clear_tab(title)
            if hist is None or not hist.scan_done.is_set():
                self._loading_label(box)
                continue
            r = hist.results
            grid = self._make_grid()
            box.append(grid)

            if title == self._TAB_CAREER:
                c = r.get("career", {})
                self._add_grid_rows(grid, [
                    {"label": "Bodies scanned",    "value": _fmt(c.get("bodies_scanned", 0))},
                    {"label": "Stars scanned",     "value": _fmt(c.get("stars_scanned", 0))},
                    {"label": "First discoveries", "value": _fmt(c.get("first_discoveries", 0))},
                    {"label": "First mapped",      "value": _fmt(c.get("first_mapped", 0))},
                    {"label": "─── Notable ───",   "value": ""},
                    {"label": "  Earth-Like",      "value": _fmt(c.get("elw", 0))},
                    {"label": "  Water World",     "value": _fmt(c.get("water_world", 0))},
                    {"label": "  Ammonia World",   "value": _fmt(c.get("ammonia_world", 0))},
                    {"label": "  Terraformable",   "value": _fmt(c.get("terraformable", 0))},
                    {"label": "  Neutron Star",    "value": _fmt(c.get("neutron_star", 0))},
                    {"label": "  Black Hole",      "value": _fmt(c.get("black_hole", 0))},
                ])

            elif title == self._TAB_POWERPLAY:
                pp    = r.get("powerplay", {})
                # Live total from state is more current than journal scan total
                live_total = getattr(self.core.state, "pp_merits_total", None)
                journal_total = pp.get("total_merits", 0)
                display_total = live_total if live_total else journal_total
                power = getattr(self.core.state, "pp_power", None) or ""
                rank  = getattr(self.core.state, "pp_rank", None)

                rows = []
                if power:
                    rows.append({"label": "Power",        "value": power})
                if rank is not None:
                    rows.append({"label": "Rank",         "value": str(rank)})
                rows.append(    {"label": "Total merits", "value": _fmt(display_total)})
                rows.append(    {"label": "─── By system (earned) ───", "value": ""})
                sys_merits = pp.get("system_merits", {})
                total_tracked = sum(sys_merits.values())
                for system, merits in list(sys_merits.items())[:25]:
                    pct = f"{merits / total_tracked * 100:.0f}%" if total_tracked else ""
                    rows.append({"label": f"  {system}", "value": _fmt(merits), "rate": pct})
                self._add_grid_rows(grid, rows)
