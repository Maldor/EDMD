"""tui/blocks/cargo.py — Cargo manifest block.

Shows cargo items with galactic average price from the last docked market.
Target market search is not available in TUI mode; use GTK4 for that workflow.
"""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SecHdr


class CargoBlock(TuiBlock):
    BLOCK_TITLE = "CARGO"

    def _compose_body(self) -> ComposeResult:
        yield Label("", id="cargo-hdr", classes="section-hdr")
        with VerticalScroll():
            yield Label("[dim]No cargo[/dim]", id="cargo-body-empty")

    def refresh_data(self) -> None:
        s     = self.state
        items = getattr(s, "cargo_items",    {})
        cap   = getattr(s, "cargo_capacity", 0)
        used  = sum(i.get("count", 0) for i in items.values())

        hdr = f"{used}/{cap} t" if cap else (f"{used} t" if used else "—")
        self._set_label("cargo-hdr", hdr)

        try:
            scroll = self.query_one(VerticalScroll)
        except Exception:
            return

        scroll.remove_children()

        if not items:
            scroll.mount(Label("[dim]No cargo[/dim]", classes="dim"))
            return

        mkt_comms = getattr(s, "cargo_market_info", {}).get("commodities", {})
        has_prices = bool(mkt_comms)

        # Group items by category
        grouped: dict[str, list] = {}
        for key, info in items.items():
            mkt     = mkt_comms.get(key, {})
            cat     = mkt.get("category_local") or info.get("category", "Uncategorised")
            name    = mkt.get("name_local")     or info.get("name",     "Unknown")
            count   = info.get("count", 0)
            avg     = mkt.get("mean_price", 0)
            stolen  = info.get("stolen", False)
            grouped.setdefault(cat, []).append(
                dict(name=name, count=count, avg=avg, stolen=stolen, key=key)
            )

        rows: list = []
        total_avg_val = 0
        for cat in sorted(grouped):
            rows.append(SecHdr(cat))
            for info in sorted(grouped[cat], key=lambda x: x["name"].lower()):
                name   = ("[red]⚠[/red] " if info["stolen"] else "") + info["name"]
                count  = info["count"]
                avg    = info["avg"]
                total_avg_val += avg * count
                if has_prices and avg:
                    val_str = f"{count} t  [dim]{self._fmt_cr(avg)}[/dim]"
                else:
                    val_str = f"{count} t"
                rows.append(KVRow(name, val_str))

        if has_prices and total_avg_val:
            rows.append(KVRow("[dim]Gal. avg total[/dim]",
                              self._fmt_cr(total_avg_val), "val"))

        scroll.mount(*rows)

    @staticmethod
    def _fmt_cr(val) -> str:
        if not val:          return "—"
        if val >= 1_000_000: return f"{val/1_000_000:.1f}M cr"
        if val >= 1_000:     return f"{val/1_000:.0f}K cr"
        return f"{int(val):,} cr"

    def _set_label(self, wid: str, text: str) -> None:
        try:
            self.query_one(f"#{wid}", Label).update(text)
        except Exception:
            pass
