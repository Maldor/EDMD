"""tui/blocks/cargo.py — Cargo manifest block with target market search."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label, Static
from textual.containers import VerticalScroll, Horizontal
from tui.block_base     import TuiBlock, KVRow, SecHdr


class CargoBlock(TuiBlock):
    BLOCK_TITLE = "CARGO"

    def _compose_body(self) -> ComposeResult:
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
            try:
                self.query_one("#cargo-target-lbl", Label).update(
                    f"[dim]→ {name}[/dim]" if name else ""
                )
            except Exception:
                pass

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

        cap_str = f"{used}/{cap} t" if cap else (f"{used} t" if used else "—")

        # ── Target market label — kept in sync with state every refresh ──────
        tgt = getattr(s, "cargo_target_market_name", "") or ""
        try:
            self.query_one("#cargo-target-lbl", Label).update(
                f"[dim]→ {tgt}[/dim]" if tgt else "[dim]No target set[/dim]"
            )
        except Exception:
            pass

        try:
            scroll = self.query_one("#cargo-scroll", VerticalScroll)
        except Exception:
            return
        scroll.remove_children()

        if not items:
            scroll.mount(Label(f"[dim]{cap_str}  No cargo[/dim]", classes="dim"))
            return

        mkt_comms  = getattr(s, "cargo_market_info", {}).get("commodities", {})
        has_prices = bool(mkt_comms)

        grouped: dict[str, list] = {}
        for key, info in items.items():
            mkt    = mkt_comms.get(key, {})
            cat    = (mkt.get("category_local")
                      or info.get("category_local")
                      or info.get("category")
                      or "Other")
            name   = (mkt.get("name_local")
                      or info.get("name_local")
                      or key.replace("_", " ").title())
            count  = info.get("count", 0)
            avg    = mkt.get("mean_price", 0)
            stolen = info.get("stolen", False)
            grouped.setdefault(cat, []).append(
                dict(name=name, count=count, avg=avg, stolen=stolen, key=key)
            )

        rows: list = []
        total_avg_val = 0
        for cat in sorted(grouped):
            rows.append(SecHdr(cat))
            for info in sorted(grouped[cat], key=lambda x: x["name"].lower()):
                name   = ("⚠ " if info["stolen"] else "") + info["name"]
                count  = info["count"]
                avg    = info["avg"]
                total_avg_val += avg * count
                val_str = (f"{count} t  [dim]{self._fmt_cr(avg)}[/dim]"
                           if has_prices and avg else f"{count} t")
                rows.append(KVRow(name, val_str))

        if has_prices and total_avg_val:
            rows.append(KVRow("[dim]Gal. avg total[/dim]",
                              self._fmt_cr(total_avg_val)))
        rows.append(KVRow("[dim]Total[/dim]", cap_str))

        scroll.mount(*rows)

    @staticmethod
    def _fmt_cr(val) -> str:
        if not val:          return "—"
        if val >= 1_000_000: return f"{val / 1_000_000:.1f}M cr"
        if val >= 1_000:     return f"{val / 1_000:.0f}K cr"
        return f"{int(val):,} cr"
