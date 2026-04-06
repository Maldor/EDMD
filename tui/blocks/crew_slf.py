"""tui/blocks/crew_slf.py — NPC Crew and SLF status block."""
from __future__ import annotations
from datetime import datetime, timezone
from textual.app       import ComposeResult
from textual.widgets   import Label
from textual.containers import VerticalScroll
from tui.block_base    import TuiBlock, KVRow, SepRow, _health_cls, _fmt_credits
from gui.helpers       import hull_css, fmt_crew_active, PP_RANK_NAMES


class CrewSlfBlock(TuiBlock):
    BLOCK_TITLE = "CREW / SLF"

    def _compose_body(self) -> ComposeResult:
        yield Label("", id="crew-hdr1", classes="section-hdr")
        yield Label("", id="crew-hdr2", classes="dim")
        with VerticalScroll():
            yield KVRow("SLF",    id="kv-slf")
            yield SepRow()
            yield KVRow("Hired",  id="kv-hired")
            yield KVRow("Active", id="kv-active")
            yield KVRow("Paid",   id="kv-paid")

    def refresh_data(self) -> None:
        s        = self.state
        has_crew = bool(s.crew_name) and s.crew_active
        # Always keep the block visible — hiding it collapses the allocated 18%
        # in the fixed TUI layout, leaving a blank gap.  Show a placeholder instead.
        if not has_crew:
            self._lbl("crew-hdr1", "No NPC crew")
            self._lbl("crew-hdr2", "")
            return

        # ── Header ────────────────────────────────────────────────────────────
        slf_full = s.slf_type or ""
        if "(" in slf_full and slf_full.endswith(")"):
            paren       = slf_full.index("(")
            slf_base    = slf_full[:paren].strip()
            slf_variant = slf_full[paren + 1:-1].strip()
        else:
            slf_base    = slf_full
            slf_variant = ""

        hdr = f"CREW: {s.crew_name or 'NPC'}"
        if s.cmdr_in_slf:
            hdr += f"  [IN {s.pilot_ship or 'FIGHTER'}]"
        self._lbl("crew-hdr1", f"{hdr}  {slf_base}" if slf_base else hdr)

        rank_str = ""
        if s.crew_rank is not None and 0 <= s.crew_rank < len(PP_RANK_NAMES):
            rank_str = f"Combat Rank: {PP_RANK_NAMES[s.crew_rank]}"
            if slf_variant:
                rank_str += f"  ({slf_variant})"
        self._lbl("crew-hdr2", rank_str)

        # ── SLF status ────────────────────────────────────────────────────────
        has_bay = s.has_fighter_bay
        try:
            self.query_one("#kv-slf", KVRow).display = has_bay
        except Exception:
            pass
        if has_bay:
            all_spent = (
                s.slf_stock_total > 0
                and s.slf_destroyed_count >= s.slf_stock_total
                and not s.slf_docked and not s.slf_deployed
            )
            if s.cmdr_in_slf:
                hull_str = f"{s.slf_hull}%" if s.slf_hull is not None else "—"
                self._kv("kv-slf", f"CMDR Aboard  |  Hull {hull_str}", "val health-good")
            elif s.slf_docked:
                self._kv("kv-slf", "SLF Docked", "val health-good")
            elif s.slf_deployed:
                hull_str = f"Hull {s.slf_hull}%" if s.slf_hull is not None else "Hull —"
                cls = f"val {_health_cls(s.slf_hull)}" if s.slf_hull is not None else "val health-good"
                self._kv("kv-slf", hull_str, cls)
            elif all_spent:
                self._kv("kv-slf", "All Spent", "val health-crit")
            else:
                self._kv("kv-slf", "Destroyed", "val health-crit")

        # ── Context ───────────────────────────────────────────────────────────
        self._kv("kv-hired",
                 s.crew_hire_time.strftime("%d %b %Y") if s.crew_hire_time else "Unknown")
        if s.crew_hire_time:
            delta = datetime.now(timezone.utc) - s.crew_hire_time
            self._kv("kv-active", fmt_crew_active(delta))
        else:
            self._kv("kv-active", "—")

        if s.crew_total_paid and s.crew_total_paid > 0:
            prefix = "" if s.crew_paid_complete else "≥ "
            self._kv("kv-paid", f"{prefix}{_fmt_credits(s.crew_total_paid)}")
        else:
            self._kv("kv-paid", "—")

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
