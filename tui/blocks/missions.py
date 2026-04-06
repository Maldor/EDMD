"""tui/blocks/missions.py — Mission stack block."""
from __future__ import annotations
from textual.app        import ComposeResult
from textual.widgets    import Label
from textual.containers import VerticalScroll
from tui.block_base     import TuiBlock, KVRow, SecHdr, _fmt_credits


def _strip_target_type(raw: str) -> str:
    s = raw or ""
    if s.startswith("$") and s.endswith(";"):
        inner = s[1:-1]
        if "_" in inner:
            s = inner.rsplit("_", 1)[-1]
    return s.strip()


class MissionsBlock(TuiBlock):
    BLOCK_TITLE = "MISSION STACK"

    def _compose_body(self) -> ComposeResult:
        yield VerticalScroll(id="missions-scroll")

    def refresh_data(self) -> None:
        s      = self.state
        detail = getattr(s, "mission_detail_map", {}) or {}

        try:
            scroll = self.query_one("#missions-scroll", VerticalScroll)
        except Exception:
            return
        scroll.remove_children()

        if not detail:
            scroll.mount(Label("[dim]No active massacre missions[/dim]", classes="dim"))
            return

        factions:        dict[str, dict] = {}
        target_factions: set[str]        = set()
        target_types:    set[str]        = set()
        total_reward                     = 0

        for mid, info in detail.items():
            src     = info.get("faction", "Unknown")
            kc      = int(info.get("kill_count", 0))
            reward  = int(info.get("reward", 0))
            tgt_f   = info.get("target_faction", "")
            tgt_t   = _strip_target_type(info.get("target_type", ""))
            sess_k  = int(info.get("kills_this_session", 0))

            if src not in factions:
                factions[src] = {"kill_count": 0, "reward": 0, "session_kills": 0}
            factions[src]["kill_count"]    += kc
            factions[src]["reward"]        += reward
            factions[src]["session_kills"] += sess_k
            total_reward += reward
            if tgt_f: target_factions.add(tgt_f)
            if tgt_t: target_types.add(tgt_t)

        heights      = sorted((v["kill_count"] for v in factions.values()), reverse=True)
        stack_height = heights[0] if heights else 0
        second_h     = heights[1] if len(heights) > 1 else stack_height
        n_missions   = len(getattr(s, "active_missions", []))
        done         = getattr(s, "missions_complete", 0)
        full_stack   = self.core.app_settings.get("FullStackSize", 20)

        rows: list = []
        rows.append(KVRow("Active", f"{n_missions}/{full_stack}  [dim]{_fmt_credits(total_reward)}[/dim]"))
        if done > 0:
            rows.append(KVRow("Redirected", f"{done}/{n_missions}"))
        rows.append(SecHdr("By Source Faction"))

        for faction in sorted(factions, key=lambda f: -factions[f]["kill_count"]):
            info  = factions[faction]
            kc    = info["kill_count"]
            rew_f = info["reward"]

            delta = stack_height - kc
            if delta == 0:
                delta_str = f"Δ{second_h - kc:+d}" if second_h != kc else "★"
            else:
                delta_str = f"Δ{-delta:+d}"

            rew_str = f"{rew_f/1_000_000:.1f}M"
            rows.append(KVRow(faction, f"{kc}  [dim]{rew_str}  {delta_str}[/dim]"))

        rows.append(KVRow("[dim]Stack height[/dim]", str(stack_height)))

        if len(target_factions) > 1:
            rows.append(Label(f"[yellow]⚠ Mixed targets: {', '.join(sorted(target_factions))}[/yellow]"))
        if len(target_types) > 1:
            rows.append(Label(f"[yellow]⚠ Mixed types: {', '.join(sorted(target_types))}[/yellow]"))

        scroll.mount(*rows)
