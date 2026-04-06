"""tui/blocks/colonisation.py — Colonisation construction site tracker."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SecHdr


class ColonisationBlock(TuiBlock):
    BLOCK_TITLE = "COLONISATION"

    def _compose_body(self) -> ComposeResult:
        yield VerticalScroll(id="colon-scroll")

    def refresh_data(self) -> None:
        s       = self.state
        sites   = getattr(s, "colonisation_sites",              [])
        cargo   = getattr(s, "cargo_items",                     {})
        docked  = getattr(s, "colonisation_docked",             False)
        cur_mid = getattr(s, "_colonisation_current_market_id", None)

        try:
            scroll = self.query_one("#colon-scroll", VerticalScroll)
        except Exception:
            return
        scroll.remove_children()

        if not sites:
            scroll.mount(Label("[dim]No construction sites tracked.\nDock at a depot to begin.[/dim]",
                               classes="dim"))
            return

        rows: list = []

        active = [s_ for s_ in sites if not s_.get("complete") and not s_.get("failed")]
        done   = [s_ for s_ in sites if s_.get("complete")]
        failed = [s_ for s_ in sites if s_.get("failed")]

        for site in active:
            is_current = docked and site.get("market_id") == cur_mid
            name = site.get("station") or site.get("system", "Unknown")
            pct  = round(site.get("progress", 0.0) * 100)
            hdr_text = f"{name}  {pct}%"
            if is_current:
                hdr_text = f"▶ {hdr_text}"
            rows.append(SecHdr(hdr_text))

            resources  = site.get("resources", {})
            site_cargo = cargo if is_current else {}
            if not resources:
                rows.append(Label("  [dim](dock to load requirements)[/dim]"))
                continue

            remaining = [
                (k, inf) for k, inf in resources.items()
                if inf["provided"] < inf["required"]
            ]
            if not remaining:
                rows.append(Label("  [green]All resources delivered![/green]"))
                continue

            remaining.sort(key=lambda x: -(x[1]["required"] - x[1]["provided"]))
            total_rem = 0
            for key, info in remaining:
                display  = info.get("name") or key
                needed   = info["required"] - info["provided"]
                total_rem += needed
                c        = site_cargo.get(key, {})
                in_cargo = c.get("count", 0) if isinstance(c, dict) else int(c)
                need_str = f"{needed:,} needed"
                if in_cargo > 0:
                    can = min(in_cargo, needed)
                    need_str += f" ({can:,} in hold)"
                if in_cargo >= needed:
                    kv = KVRow(display, f"[green]{need_str}[/green]")
                elif in_cargo > 0:
                    kv = KVRow(display, f"[yellow]{need_str}[/yellow]")
                else:
                    kv = KVRow(display, need_str)
                rows.append(kv)
            rows.append(KVRow("[dim]Total remaining[/dim]", f"{total_rem:,} t"))

        for site in done:
            name = site.get("station") or site.get("system", "Unknown")
            rows.append(Label(f"[green]✓ {name} — complete[/green]"))

        for site in failed:
            name = site.get("station") or site.get("system", "Unknown")
            rows.append(Label(f"[red]✗ {name} — failed[/red]"))

        scroll.mount(*rows)
