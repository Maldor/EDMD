"""tui/blocks/cargo.py — Cargo manifest block with target market search."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label, Static
from textual.containers import VerticalScroll, Horizontal
from tui.block_base     import TuiBlock, KVRow, SecHdr


def _fmt_cr(v) -> str:
    if not v: return "—"
    v = int(v)
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.2f}B cr"
    if v >= 1_000_000:     return f"{v/1_000_000:.1f}M cr"
    if v >= 1_000:         return f"{v/1_000:.0f}K cr"
    return f"{v:,} cr"


class CargoBlock(TuiBlock):
    BLOCK_TITLE = "CARGO"

    def compose(self) -> ComposeResult:
        # Header row: left = "CARGO", right = price source label
        with Horizontal(id="cargo-hdr-row"):
            yield Label(" CARGO ", id="cargo-title", classes="block-title")
            yield Label("", id="cargo-price-src", classes="block-title")
        with VerticalScroll(id="cargo-scroll"):
            yield Label("[dim]No cargo[/dim]", id="cargo-empty")
        with Horizontal(id="cargo-footer"):
            yield Static(">> Set Target", id="cargo-target-btn",
                         classes="footer-lbl")
            yield Label("", id="cargo-target-lbl", classes="dim")

    def on_click(self, event) -> None:
        if str(getattr(event.widget, "id", "")) != "cargo-target-btn":
            return
        event.stop()
        spansh = self.core._plugins.get("spansh")
        if spansh is None:
            return

        def _on_select(result: dict | None) -> None:
            if not result:
                return
            name = result.get("name", "")
            spansh.set_target(
                name,
                result.get("system", ""),
                _record=result,
            )

        from tui.search_modal import SearchModal
        self.app.push_screen(SearchModal(
            title        = "Set Target Market",
            placeholder  = "Station name…",
            search_fn    = spansh.search,
            result_label = lambda r: (
                f"{r['name']}  [dim]{r.get('system', '')}[/dim]"
            ),
            callback     = _on_select,
        ))

    def refresh_data(self) -> None:
        s     = self.state
        items = getattr(s, "cargo_items",    {})
        cap   = getattr(s, "cargo_capacity", 0)
        used  = sum(i.get("count", 0) for i in items.values())

        # ── Price source label (top-right of header) ──────────────────────────
        tgt_info  = getattr(s, "cargo_target_market", {})
        tgt_name  = getattr(s, "cargo_target_market_name", "") or ""
        mkt_info  = getattr(s, "cargo_market_info", {})
        tgt_comms = tgt_info.get("commodities", {})
        gal_comms = mkt_info.get("commodities", {})
        # has_target_name: user has selected a station (show its name in header)
        # has_target_prices: station market data was loaded (use for prices)
        has_target_name   = bool(tgt_name)
        has_target_prices = has_target_name and bool(tgt_comms)

        if has_target_name:
            stn  = tgt_info.get("station_name", "") or ""
            sys_ = tgt_info.get("star_system",  "") or ""
            src_label = f"{stn} | {sys_}" if stn and sys_ else (tgt_name or "Target")
        else:
            stn  = mkt_info.get("station_name", "") or ""
            sys_ = mkt_info.get("star_system",  "") or ""
            src_label = (f"{stn} | {sys_}" if stn and sys_ else
                         stn or sys_ or "Gal. Avg")

        try:
            self.query_one("#cargo-price-src", Label).update(
                f" [dim]{src_label}[/dim] "
            )
        except Exception:
            pass

        # ── Target label in footer ────────────────────────────────────────────
        try:
            self.query_one("#cargo-target-lbl", Label).update(
                f"[dim]→ {tgt_name}[/dim]" if tgt_name else "[dim]No target set[/dim]"
            )
        except Exception:
            pass

        try:
            scroll = self.query_one("#cargo-scroll", VerticalScroll)
        except Exception:
            return
        scroll.remove_children()

        cap_str = f"{used}/{cap} t" if cap else (f"{used} t" if used else "—")

        if not items:
            scroll.mount(Label(f"[dim]{cap_str}  No cargo[/dim]", classes="dim"))
            return

        # ── Build enriched item list ──────────────────────────────────────────
        enriched = []
        for key, info in items.items():
            gal  = gal_comms.get(key, {})
            tgt  = tgt_comms.get(key, {})
            cat  = (gal.get("category_local")
                    or tgt.get("category_local")
                    or info.get("category_local")
                    or info.get("category")
                    or "Other")
            name = (gal.get("name_local")
                    or tgt.get("name_local")
                    or info.get("name_local")
                    or key.replace("_", " ").title())
            count    = info.get("count", 0)
            gal_avg  = int(gal.get("mean_price", 0))
            tgt_sell = int(tgt.get("sell_price", 0))
            # Price priority: target station sell > docked market sell > galactic avg
            docked_sell = int(gal.get("sell_price", 0))
            if has_target_prices:
                price = tgt_sell or gal_avg
            else:
                price = docked_sell or gal_avg
            stolen = info.get("stolen", False)
            enriched.append(dict(name=name, cat=cat, count=count,
                                 price=price, stolen=stolen))

        enriched.sort(key=lambda x: (x["cat"].lower(), x["name"].lower()))

        # ── Render rows: qty  |  credits ─────────────────────────────────────
        rows: list = []
        current_cat = None
        total = 0

        for item in enriched:
            if item["cat"] != current_cat:
                current_cat = item["cat"]
                rows.append(SecHdr(current_cat))
            count  = item["count"]
            price  = item["price"]
            total += price * count
            name   = ("⚠ " if item["stolen"] else "") + item["name"]
            # qty right-padded to 4 so the | aligns across all rows
            val_str = f"{count:>4} t  [dim]|  {_fmt_cr(price)}[/dim]"
            rows.append(KVRow(name, val_str))

        # Totals row: same fixed-width column format as item rows so qty aligns
        cr_total = _fmt_cr(total) if total else "—"
        rows.append(KVRow("[dim]Totals[/dim]",
                          f"{used:>4} t  [dim]|  {cr_total}[/dim]"))

        scroll.mount(*rows)
