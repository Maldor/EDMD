"""tui/blocks/assets.py — Wallet, ships, modules, carrier, at-risk holdings."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label, TabbedContent, TabPane
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SepRow, SecHdr, _fmt_credits


class AssetsBlock(TuiBlock):
    BLOCK_TITLE = "ASSETS"

    def _compose_body(self) -> ComposeResult:
        with TabbedContent(id="assets-tabs"):

            with TabPane("Wallet", id="assets-tab-wallet"):
                with VerticalScroll():
                    yield SecHdr("Currencies")
                    yield KVRow("Credits",              id="aw-credits")
                    yield SepRow()
                    yield SecHdr("Fleet")
                    yield KVRow("Ships",                id="aw-ships")
                    yield KVRow("Modules",              id="aw-modules")
                    yield SepRow()
                    yield SecHdr("Assets at Risk")
                    yield KVRow("Bounties",             id="aw-bounties")
                    yield KVRow("Combat bonds",         id="aw-bonds")
                    yield KVRow("Trade vouchers",       id="aw-trade")
                    yield KVRow("Cartography (est.)",  id="aw-carto")
                    yield KVRow("Exobiology (est.)",   id="aw-exobio")
                    yield SepRow()
                    yield KVRow("Net Worth",            id="aw-networth", val_classes="val")

            with TabPane("Ships", id="assets-tab-ships"):
                with VerticalScroll():
                    yield Label("[dim]—[/dim]", id="assets-ships")

            with TabPane("Modules", id="assets-tab-modules"):
                with VerticalScroll():
                    yield Label("[dim]No stored modules[/dim]", id="assets-modules")

            with TabPane("Fleet Carrier", id="assets-tab-carrier"):
                with VerticalScroll():
                    yield KVRow("Name",      id="ac-name")
                    yield KVRow("Callsign",  id="ac-callsign")
                    yield KVRow("System",    id="ac-system")
                    yield KVRow("Fuel",      id="ac-fuel")
                    yield SepRow()
                    yield SecHdr("Finance")
                    yield KVRow("Balance",   id="ac-balance")
                    yield KVRow("Reserve",   id="ac-reserve")
                    yield KVRow("Upkeep/wk", id="ac-upkeep")
                    yield SepRow()
                    yield SecHdr("Cargo")
                    yield KVRow("Stored",    id="ac-stored")
                    yield KVRow("Free",      id="ac-free")

    def refresh_data(self) -> None:
        self._refresh_wallet()
        self._refresh_ships()
        self._refresh_modules()
        self._refresh_carrier()

    # ── Wallet ────────────────────────────────────────────────────────────────

    def _refresh_wallet(self) -> None:
        s       = self.state
        bal     = getattr(s, "assets_balance", None)
        current = getattr(s, "assets_current_ship",  None)
        stored  = list(getattr(s, "assets_stored_ships", []))
        cid     = (current or {}).get("ship_id")
        if cid:
            stored = [x for x in stored if x.get("ship_id") != cid]
        all_ships = ([current] if current else []) + stored
        ships_val = sum(x.get("value", 0) for x in all_ships if x)
        mods_val  = sum(m.get("value", 0)
                        for m in getattr(s, "assets_stored_modules", []))

        h = {
            "bounties": getattr(s, "holdings_bounties",    0),
            "bonds":    getattr(s, "holdings_bonds",       0),
            "trade":    getattr(s, "holdings_trade",       0),
            "carto":    getattr(s, "holdings_cartography", 0),
            "exobio":   getattr(s, "holdings_exobiology",  0),
        }
        nw = (bal or 0) + ships_val + mods_val + sum(h.values())

        self._kv("aw-credits", _fmt_credits(bal))
        self._kv("aw-ships",   _fmt_credits(ships_val))
        self._kv("aw-modules", _fmt_credits(mods_val))
        self._kv("aw-bounties", _fmt_credits(h["bounties"]))
        self._kv("aw-bonds",    _fmt_credits(h["bonds"]))
        self._kv("aw-trade",    _fmt_credits(h["trade"]))
        self._kv("aw-carto",    _fmt_credits(h["carto"]))
        self._kv("aw-exobio",   _fmt_credits(h["exobio"]))
        self._kv("aw-networth", _fmt_credits(nw))

    # ── Ships ─────────────────────────────────────────────────────────────────

    def _refresh_ships(self) -> None:
        s       = self.state
        current = getattr(s, "assets_current_ship", None)
        stored  = list(getattr(s, "assets_stored_ships", []))
        cid     = (current or {}).get("ship_id")
        if cid:
            stored = [x for x in stored if x.get("ship_id") != cid]
        all_ships = ([current] if current else []) + stored

        if not all_ships:
            self._lbl("assets-ships", "[dim]No ship data[/dim]")
            return

        lines: list[str] = []
        for i, ship in enumerate(all_ships):
            if ship is None:
                continue
            name  = ship.get("type_display") or ship.get("type", "Unknown")
            ident = ship.get("name", "")
            val   = ship.get("value", 0)
            loc   = ship.get("station") or ship.get("system") or ""
            tag   = "[green]▶ CURRENT[/green]  " if i == 0 else ""
            lines.append(f"{tag}[bold]{name}[/bold]"
                         + (f"  [dim]{ident}[/dim]" if ident else "")
                         + f"  {_fmt_credits(val)}")
            if loc:
                lines.append(f"  [dim]{loc}[/dim]")
        self._lbl("assets-ships", "\n".join(lines) or "[dim]No ships[/dim]")

    # ── Modules ───────────────────────────────────────────────────────────────

    def _refresh_modules(self) -> None:
        modules = getattr(self.state, "assets_stored_modules", [])
        if not modules:
            self._lbl("assets-modules", "[dim]No stored modules[/dim]")
            return

        by_system: dict[str, list] = {}
        for m in modules:
            sys = m.get("system") or "Unknown"
            by_system.setdefault(sys, []).append(m)

        lines: list[str] = []
        for sys in sorted(by_system):
            lines.append(f"[bold]{sys.upper()}[/bold]")
            for m in sorted(by_system[sys],
                            key=lambda x: x.get("name_display", "").lower()):
                name = m.get("name_display") or m.get("name_internal", "Unknown")
                val  = m.get("value", 0)
                eng  = m.get("engineering", {})
                bp   = eng.get("BlueprintName", "")
                lv   = eng.get("Level")
                hot  = m.get("hot", False)
                tag  = "[red]⚠ [/red]" if hot else "  "
                eng_tag = f"  [dim]G{lv}[/dim]" if (bp and lv) else ""
                lines.append(f"{tag}[dim]{name}[/dim]{eng_tag}  {_fmt_credits(val)}")
        self._lbl("assets-modules", "\n".join(lines).rstrip())

    # ── Carrier ───────────────────────────────────────────────────────────────

    def _refresh_carrier(self) -> None:
        carrier = getattr(self.state, "assets_carrier", None)
        if not carrier:
            for wid in ("ac-name","ac-callsign","ac-system","ac-fuel",
                        "ac-balance","ac-reserve","ac-upkeep",
                        "ac-stored","ac-free"):
                self._kv(wid, "—")
            return

        fuel = int(carrier.get("fuel", 0) or 0)
        self._kv("ac-name",     carrier.get("name",     "—") or "—")
        self._kv("ac-callsign", carrier.get("callsign", "—") or "—")
        self._kv("ac-system",   carrier.get("system",   "—") or "—")
        self._kv("ac-fuel",     f"{fuel}/1000  ({fuel//10}%)")
        self._kv("ac-balance",  _fmt_credits(carrier.get("balance")))
        self._kv("ac-reserve",  _fmt_credits(carrier.get("reserve_balance")))
        self._kv("ac-upkeep",   _fmt_credits(carrier.get("coreCost")))
        cap  = carrier.get("capacity", {})
        used = cap.get("cargo", 0)
        free = cap.get("freeSpace", 0)
        self._kv("ac-stored", str(used) if (used or free) else "—")
        self._kv("ac-free",   str(free) if (used or free) else "—")

    # ── Helpers ───────────────────────────────────────────────────────────────

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
