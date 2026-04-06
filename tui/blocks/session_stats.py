"""tui/blocks/session_stats.py — Session statistics block."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label, TabbedContent, TabPane
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SecHdr, SepRow


class SessionStatsBlock(TuiBlock):
    BLOCK_TITLE = "SESSION STATS"

    def _compose_body(self) -> ComposeResult:
        with TabbedContent(id="ss-tabs"):
            with TabPane("Summary", id="ss-tab-summary"):
                yield VerticalScroll(id="ss-summary-scroll")

    def refresh_data(self) -> None:
        core      = self.core
        providers = getattr(core, "session_providers", [])
        plugin    = core._plugins.get("session_stats")
        dur_s     = plugin.session_duration_seconds() if plugin else 0.0

        try:
            scroll = self.query_one("#ss-summary-scroll", VerticalScroll)
        except Exception:
            return
        scroll.remove_children()

        rows: list = []
        if dur_s > 0:
            rows.append(KVRow("Duration", self.fmt_duration(dur_s)))

        for p in providers:
            if not hasattr(p, "get_summary_rows") or not p.has_activity():
                continue
            title = getattr(p, "ACTIVITY_TAB_TITLE", "")
            if title:
                rows.append(SecHdr(title))
            for row in p.get_summary_rows():
                lbl  = row.get("label", "")
                val  = row.get("value", "—")
                rate = row.get("rate")
                if lbl.startswith("─"):
                    rows.append(SepRow())
                elif rate:
                    rows.append(KVRow(lbl, f"{val}  [dim]{rate}[/dim]"))
                else:
                    rows.append(KVRow(lbl, val))

        if not rows:
            rows.append(Label("[dim]No session data[/dim]", classes="dim"))
        scroll.mount(*rows)

        self._rebuild_activity_tabs(providers)

    def _rebuild_activity_tabs(self, providers) -> None:
        tabs = self.query_one("#ss-tabs", TabbedContent)
        for pane in list(tabs.query(TabPane)):
            if str(pane.id) != "ss-tab-summary":
                pane.remove()

        for p in providers:
            if not hasattr(p, "get_tab_rows") or not p.has_activity():
                continue
            tab_rows = p.get_tab_rows()
            if not tab_rows:
                continue
            title    = getattr(p, "ACTIVITY_TAB_TITLE", "Activity")
            pane_id  = f"ss-tab-{title.lower().replace(' ', '_')}"
            kv_rows: list = []
            for row in tab_rows:
                lbl  = row.get("label", "")
                val  = row.get("value", "—")
                rate = row.get("rate")
                if lbl.startswith("─"):
                    kv_rows.append(SepRow())
                elif rate:
                    kv_rows.append(KVRow(lbl, f"{val}  [dim]{rate}[/dim]"))
                else:
                    kv_rows.append(KVRow(lbl, val))

            # Pass content to TabPane constructor so ContentSwitcher sees a
            # fully-populated pane the moment add_pane registers it.
            tab_pane = TabPane(title, VerticalScroll(*kv_rows), id=pane_id)
            tabs.add_pane(tab_pane)
