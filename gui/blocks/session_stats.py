"""
gui/blocks/session_stats.py — Tabbed session statistics block.

Summary tab: duration + collected rows from all active activity providers.
Activity tabs: one per registered provider that has_activity(), sorted A-Z.

Row format from providers:
    {"label": str, "value": str, "rate": str | None}
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

    _TAB_SUMMARY = "Summary"

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)

        # Tab bar
        self._tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar.add_css_class("mat-tab-bar")
        body.append(self._tab_bar)

        # Content stack — one page per tab
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        body.append(self._stack)

        self._tab_btns: dict[str, Gtk.Button] = {}
        self._active_tab: str = self._TAB_SUMMARY

        # Build the permanent Summary tab
        self._build_tab(self._TAB_SUMMARY)
        self._set_active_tab(self._TAB_SUMMARY)

    def _build_tab(self, title: str) -> Gtk.Box:
        """Create a scrollable tab page and its button. Return the content box."""
        # Tab button
        btn = Gtk.Button(label=title)
        btn.add_css_class("mat-tab-btn")
        btn.connect("clicked", lambda _b, t=title: self._set_active_tab(t))
        self._tab_bar.append(btn)
        self._tab_btns[title] = btn

        # Content box inside a scrolled window.
        # margin_end=12 keeps text clear of the GTK4 overlay scrollbar track.
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

    def _get_or_create_tab(self, title: str) -> Gtk.Box:
        """Return the content box for a tab, creating it if needed."""
        page = self._stack.get_child_by_name(title)
        if page is not None:
            # GTK4: ScrolledWindow → Viewport → Box
            vp = page.get_child()
            return vp.get_child() if hasattr(vp, "get_child") else vp
        return self._build_tab(title)

    def _clear_tab(self, title: str) -> Gtk.Box:
        """Clear and return the content box for a tab."""
        page = self._stack.get_child_by_name(title)
        if page is not None:
            # GTK4: ScrolledWindow → Viewport → Box
            vp    = page.get_child()
            inner = vp.get_child() if hasattr(vp, "get_child") else vp
            child = inner.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                inner.remove(child)
                child = nxt
            return inner
        return self._get_or_create_tab(title)

    def _remove_stale_tabs(self, active_titles: set) -> None:
        """Remove tabs for providers that no longer have activity."""
        to_remove = [t for t in self._tab_btns if t not in active_titles]
        for t in to_remove:
            btn = self._tab_btns.pop(t)
            self._tab_bar.remove(btn)
            page = self._stack.get_child_by_name(t)
            if page:
                self._stack.remove(page)
        if self._active_tab not in self._tab_btns:
            self._set_active_tab(self._TAB_SUMMARY)

    def _append_rows(self, box: Gtk.Box, rows: list[dict]) -> None:
        """Append provider rows to a content box."""
        # Column widths
        tw = max((len(r["label"]) for r in rows), default=8)
        vw = max((len(r["value"]) for r in rows), default=4)

        for r in rows:
            label = r["label"]
            value = r["value"]
            rate  = r.get("rate")

            # Section dividers
            if not value and not rate:
                sep = Gtk.Label(label=label)
                sep.add_css_class("data-key")
                sep.set_xalign(0.0)
                sep.set_margin_top(4)
                box.append(sep)
                continue

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row_box.add_css_class("data-row")

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("data-key")
            lbl.set_xalign(0.0)
            lbl.set_hexpand(True)
            row_box.append(lbl)

            if rate:
                # value | rate /hr layout
                line = Gtk.Label(label=f"{value}  |  {rate}")
                line.add_css_class("stat-line")
                line.set_xalign(1.0)
                row_box.append(line)
            else:
                val_lbl = Gtk.Label(label=value)
                val_lbl.add_css_class("data-value")
                val_lbl.set_xalign(1.0)
                row_box.append(val_lbl)

            box.append(row_box)

    def refresh(self) -> None:
        core      = self.core
        providers = getattr(core, "session_providers", [])
        plugin    = core._plugins.get("session_stats")

        # --- Summary tab ---
        summary_box = self._clear_tab(self._TAB_SUMMARY)

        # Duration row (always first)
        dur_s = plugin.session_duration_seconds() if plugin else 0.0
        dur_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dur_row.add_css_class("data-row")
        dur_key = Gtk.Label(label="Duration")
        dur_key.add_css_class("data-key")
        dur_key.set_hexpand(True)
        dur_row.append(dur_key)
        dur_val = Gtk.Label(label=self.fmt_duration(dur_s) if dur_s > 0 else "—")
        dur_val.add_css_class("data-value")
        dur_row.append(dur_val)
        summary_box.append(dur_row)

        # Collect summary rows from all active providers
        all_summary: list[dict] = []
        for p in providers:
            if p.has_activity():
                rows = p.get_summary_rows()
                if rows:
                    all_summary.extend(rows)

        if all_summary:
            summary_box.append(
                Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            )
            self._append_rows(summary_box, all_summary)

        # --- Activity tabs ---
        active_tab_titles = {self._TAB_SUMMARY}
        for p in providers:
            if not p.has_activity():
                continue
            tab_rows = p.get_tab_rows()
            if not tab_rows:
                continue
            title = getattr(p, "ACTIVITY_TAB_TITLE", "Activity")
            active_tab_titles.add(title)
            tab_box = self._clear_tab(title)
            self._append_rows(tab_box, tab_rows)

        self._remove_stale_tabs(active_tab_titles)
