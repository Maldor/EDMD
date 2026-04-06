"""tui/blocks/career.py — Career lifetime statistics block."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label, TabbedContent, TabPane
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SepRow, _fmt, _fmt_credits


class CareerBlock(TuiBlock):
    BLOCK_TITLE = "CAREER"

    def _compose_body(self) -> ComposeResult:
        with TabbedContent(id="career-tabs"):

            with TabPane("Summary", id="career-pane-summary"):
                with VerticalScroll():
                    yield Label("[dim]Scanning journals…[/dim]", id="career-summary")

            with TabPane("Combat", id="career-pane-combat"):
                with VerticalScroll():
                    yield KVRow("Kills",        id="cc-kills")
                    yield KVRow("Bounties",     id="cc-bounties")
                    yield KVRow("Combat bonds", id="cc-bonds")
                    yield KVRow("Deaths",       id="cc-deaths")

            with TabPane("Exploration", id="career-pane-expl"):
                with VerticalScroll():
                    yield KVRow("Systems visited",  id="ce-systems")
                    yield KVRow("Total jumps",      id="ce-jumps")
                    yield KVRow("Max distance",     id="ce-dist")
                    yield KVRow("Planets DSS",      id="ce-dss")
                    yield KVRow("Cartography",      id="ce-carto")

            with TabPane("Exobiology", id="career-pane-exo"):
                with VerticalScroll():
                    yield KVRow("Samples", id="cex-samples")
                    yield KVRow("Sold",    id="cex-sold")

            with TabPane("Mining", id="career-pane-mining"):
                with VerticalScroll():
                    yield KVRow("Quantity mined", id="cm-qty")
                    yield KVRow("Profit",         id="cm-profit")

            with TabPane("Trade", id="career-pane-trade"):
                with VerticalScroll():
                    yield KVRow("Profit",  id="ct-profit")
                    yield KVRow("Markets", id="ct-markets")

            with TabPane("PowerPlay", id="career-pane-pp"):
                with VerticalScroll():
                    yield KVRow("Merits total", id="cp-merits")
                    yield Label("",             id="cp-by-system")

    def refresh_data(self) -> None:
        hist = self.core._plugins.get("journal_history")

        if hist is None or not hist.scan_done.is_set():
            self._lbl("career-summary", "[dim]Scanning journals…[/dim]")
            return

        r     = hist.results
        stats = r.get("statistics", {})
        expl  = stats.get("Exploration",  {})
        exo   = stats.get("Exobiology",   {})
        cmb   = stats.get("Combat",       {})
        mine  = stats.get("Mining",       {})
        trd   = stats.get("Trading",      {})
        pp    = r.get("powerplay",        {})

        from core.emit import fmt_duration

        # ── Summary (dynamic sections — kept as single Label) ──────────────────
        time_s  = expl.get("Time_Played", 0)
        summary = []
        if time_s:
            summary.append(f"[dim]Time played[/dim]  {fmt_duration(int(time_s))}")

        kills = cmb.get("Bounties_Claimed", 0)
        bp    = cmb.get("Bounty_Hunting_Profit", 0)
        if kills or bp:
            summary += ["", "[bold]COMBAT[/bold]",
                        f"  [dim]Kills[/dim]    {_fmt(kills)}  "
                        f"[dim]|[/dim]  {_fmt_credits(bp)}"]

        sys_vis = expl.get("Systems_Visited", 0)
        ep      = expl.get("Exploration_Profits", 0)
        if sys_vis or ep:
            summary += ["", "[bold]EXPLORATION[/bold]",
                        f"  [dim]Systems[/dim]  {_fmt(sys_vis)}  "
                        f"[dim]|[/dim]  {_fmt_credits(ep)}"]

        samples = exo.get("Organic_Data", 0)
        exo_p   = exo.get("Organic_Data_Profits", 0)
        if samples or exo_p:
            summary += ["", "[bold]EXOBIOLOGY[/bold]",
                        f"  [dim]Samples[/dim]  {_fmt(samples)}  "
                        f"[dim]|[/dim]  {_fmt_credits(exo_p)}"]

        mined  = mine.get("Quantity_Mined", 0)
        mine_p = mine.get("Mining_Profits", 0)
        if mined or mine_p:
            summary += ["", "[bold]MINING[/bold]",
                        f"  [dim]Mined[/dim]    {_fmt(mined)} t  "
                        f"[dim]|[/dim]  {_fmt_credits(mine_p)}"]

        trd_p = trd.get("Market_Profits", 0)
        if trd_p:
            summary += ["", "[bold]TRADE[/bold]",
                        f"  [dim]Profit[/dim]   {_fmt_credits(trd_p)}"]

        live_merits = getattr(self.core.state, "pp_merits_total", None)
        pp_total    = live_merits if live_merits else pp.get("total_merits", 0)
        power       = getattr(self.core.state, "pp_power", None)
        if pp_total and power:
            summary += ["", "[bold]POWERPLAY[/bold]",
                        f"  [dim]Merits[/dim]   {_fmt(pp_total)}"]

        self._lbl("career-summary",
                  "\n".join(summary) or "[dim]No career data[/dim]")

        # ── Combat ────────────────────────────────────────────────────────────
        self._kv("cc-kills",    _fmt(cmb.get("Bounties_Claimed")))
        self._kv("cc-bounties", _fmt_credits(cmb.get("Bounty_Hunting_Profit")))
        self._kv("cc-bonds",    _fmt_credits(cmb.get("Combat_Bond_Profits")))
        self._kv("cc-deaths",   _fmt(cmb.get("Deaths")))

        # ── Exploration ───────────────────────────────────────────────────────
        self._kv("ce-systems", _fmt(expl.get("Systems_Visited")))
        self._kv("ce-jumps",   _fmt(expl.get("Total_Hyperdrive_Jumps")))
        dist = expl.get("Greatest_Distance_From_Start", 0)
        self._kv("ce-dist",    f"{_fmt(dist)} ly" if dist else "—")
        self._kv("ce-dss",     _fmt(expl.get("Planets_Scanned_To_Level_3")))
        self._kv("ce-carto",   _fmt_credits(expl.get("Exploration_Profits")))

        # ── Exobiology ────────────────────────────────────────────────────────
        self._kv("cex-samples", _fmt(exo.get("Organic_Data")))
        self._kv("cex-sold",    _fmt_credits(exo.get("Organic_Data_Profits")))

        # ── Mining ────────────────────────────────────────────────────────────
        mined_qty = mine.get("Quantity_Mined", 0)
        self._kv("cm-qty",    f"{_fmt(mined_qty)} t" if mined_qty else "—")
        self._kv("cm-profit", _fmt_credits(mine.get("Mining_Profits")))

        # ── Trade ─────────────────────────────────────────────────────────────
        self._kv("ct-profit",  _fmt_credits(trd.get("Market_Profits")))
        self._kv("ct-markets", _fmt(trd.get("Markets_Traded_With")))

        # ── PowerPlay ─────────────────────────────────────────────────────────
        self._kv("cp-merits", _fmt(pp_total) if pp_total else "—")
        by_sys = pp.get("by_system", {})
        if by_sys:
            lines = ["", "[bold]BY SYSTEM[/bold]"]
            for sys_name, merits in sorted(by_sys.items(), key=lambda x: -x[1]):
                lines.append(f"  [dim]{sys_name}[/dim]  {_fmt(merits)}")
            self._lbl("cp-by-system", "\n".join(lines))
        else:
            self._lbl("cp-by-system", "")

    def _kv(self, wid: str, text: str, classes: str = "val") -> None:
        try:
            self.query_one(f"#{wid}", KVRow).set_value(text, classes)
        except Exception:
            pass

    def _lbl(self, wid: str, text: str) -> None:
        try:
            self.query_one(f"#{wid}", Label).update(text)
        except Exception:
            pass
