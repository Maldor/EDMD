"""
gui/blocks/commander.py — Commander, ship, location, powerplay block.

Three-tab layout (matching Assets block pattern):
  Info  — ship identity, vitals (shields/hull/fuel), location, mode, powerplay
  Ranks — CAPI combat/trade/explore/CQC/mercenary/exobio ranks with progress
  Rep   — CAPI superpower reputation (Federation, Empire, Alliance, Independent)

Powerplay stays on the Info tab. Combat rank moves to Ranks tab.
Ranks and Rep tabs are CAPI-sourced; they stay hidden until first poll.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget
from gui.helpers    import hull_css, fmt_shield, pp_rank_progress

_TABS = [
    ("info",   "Info"),
    ("ranks",  "Ranks"),
    ("rep",    "Rep"),
]


class CommanderBlock(BlockWidget):
    BLOCK_TITLE = "Commander"
    BLOCK_CSS   = "commander-block"

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self, parent: Gtk.Box) -> None:
        # ── Two-line header ───────────────────────────────────────────────────
        hdr_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

        # Line 1: CMDR NAME — RANK (left)  |  SHIP TYPE (right)
        hdr_line1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._cmdr_header_lbl = Gtk.Label(label="COMMANDER")
        self._cmdr_header_lbl.set_xalign(0.0)
        self._cmdr_header_lbl.set_hexpand(True)
        hdr_line1.append(self._cmdr_header_lbl)
        self._cmdr_ship_type_hdr = Gtk.Label(label="")
        self._cmdr_ship_type_hdr.set_xalign(1.0)
        hdr_line1.append(self._cmdr_ship_type_hdr)
        hdr_outer.append(hdr_line1)

        # Line 2: SQUADRON NAME [TAG] (left)  |  SHIP NAME | IDENT (right)
        hdr_line2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._cmdr_squadron_lbl = Gtk.Label(label="")
        self._cmdr_squadron_lbl.set_xalign(0.0)
        self._cmdr_squadron_lbl.set_hexpand(True)
        self._cmdr_squadron_lbl.set_visible(False)
        hdr_line2.append(self._cmdr_squadron_lbl)
        self._cmdr_ship_ident_hdr = Gtk.Label(label="")
        self._cmdr_ship_ident_hdr.set_xalign(1.0)
        self._cmdr_ship_ident_hdr.set_visible(False)
        hdr_line2.append(self._cmdr_ship_ident_hdr)
        self._hdr_line2 = hdr_line2
        hdr_outer.append(hdr_line2)

        body = self._build_section(parent, title_widget=hdr_outer)

        # ── Tab scaffold ──────────────────────────────────────────────────────
        self._layout_stack = Gtk.Stack()
        self._layout_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self._layout_stack.set_vexpand(True)
        self._layout_stack.set_hexpand(True)
        body.append(self._layout_stack)

        self._tab_btns:   dict[str, Gtk.Button] = {}
        self._active_tab: str = "info"

        self._build_tabbed_layout()
        self._layout_stack.set_visible_child_name("tabbed")

    # ── Tab scaffold ───────────────────────────────────────────────────────────

    def _build_tabbed_layout(self) -> None:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_vexpand(True)

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_bar.add_css_class("mat-tab-bar")
        page.append(tab_bar)
        page.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.NONE)
        stack.set_vexpand(True)
        stack.set_hexpand(True)
        page.append(stack)
        self._tab_stack = stack

        for cat, label in _TABS:
            btn = Gtk.Button()
            btn.add_css_class("mat-tab-btn")
            btn.set_hexpand(True)
            btn.set_can_focus(False)
            tab_bar.append(btn)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("mat-tab-label")
            btn.set_child(lbl)
            btn.connect("clicked", self._on_tab_click, cat)
            self._tab_btns[cat] = btn

            if cat == "info":
                tab_page = self._build_info_tab()
            elif cat == "ranks":
                tab_page = self._build_ranks_tab()
            else:
                tab_page = self._build_rep_tab()
            stack.add_named(tab_page, cat)

        self._set_active_tab("info")
        self._layout_stack.add_named(page, "tabbed")

    # ── Info tab ───────────────────────────────────────────────────────────────

    def _build_info_tab(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(4)

        def _row(key_text):
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            r.add_css_class("data-row")
            k = self.make_label(key_text, css_class="data-key")
            k.set_hexpand(False)
            r.append(k)
            v = self.make_label("—", css_class="data-value")
            v.set_hexpand(True)
            v.set_xalign(1.0)
            r.append(v)
            box.append(r)
            return r, v

        # Shields
        row_sh = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row_sh.add_css_class("data-row")
        row_sh.append(self.make_label("Shields", css_class="data-key"))
        self._cmdr_shields = self.make_label("—", css_class="data-value")
        self._cmdr_shields.set_hexpand(True)
        self._cmdr_shields.set_xalign(1.0)
        row_sh.append(self._cmdr_shields)
        box.append(row_sh)

        # Hull
        row_hull = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row_hull.add_css_class("data-row")
        row_hull.append(self.make_label("Hull", css_class="data-key"))
        self._cmdr_hull = self.make_label("—", css_class="data-value")
        self._cmdr_hull.set_hexpand(True)
        self._cmdr_hull.set_xalign(1.0)
        row_hull.append(self._cmdr_hull)
        box.append(row_hull)

        _, self._cmdr_fuel = _row("Fuel")

        vitals_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        vitals_sep.add_css_class("vitals-sep")
        box.append(vitals_sep)

        _, self._cmdr_mode     = _row("Mode")
        _, self._cmdr_system   = _row("System")
        _, self._cmdr_location = _row("Body")
        _, self._cmdr_pp       = _row("Power")
        _, self._cmdr_pprank   = _row("PP Rank")

        # PP progress bar
        self._pp_rank_bar = Gtk.ProgressBar()
        self._pp_rank_bar.set_fraction(0.0)
        self._pp_rank_bar.add_css_class("pp-rank-bar")
        self._pp_rank_bar.set_show_text(False)
        self._pp_rank_bar.set_size_request(40, 4)
        bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar_box.add_css_class("pp-rank-bar-row")
        bar_box.append(self._pp_rank_bar)
        self._pp_rank_bar.set_hexpand(True)
        box.append(bar_box)

        return box

    # ── Ranks tab ──────────────────────────────────────────────────────────────

    def _build_ranks_tab(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("mat-tab-scroll")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.set_margin_top(4)
        box.set_margin_end(12)   # clear GTK4 overlay scrollbar track
        scroll.set_child(box)

        self._no_ranks_lbl = Gtk.Label(label="Awaiting CAPI data…")
        self._no_ranks_lbl.add_css_class("data-key")
        self._no_ranks_lbl.set_xalign(0.5)
        self._no_ranks_lbl.set_margin_top(8)
        box.append(self._no_ranks_lbl)

        # dict: capi_key -> (row_box, value_label, progress_bar, bar_wrapper)
        self._rank_rows: dict = {}

        from core.state import CAPI_RANK_SKILLS
        for capi_key, display_label, _table in CAPI_RANK_SKILLS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row.add_css_class("data-row")
            k = self.make_label(display_label, css_class="data-key")
            k.set_hexpand(False)
            row.append(k)
            v = self.make_label("—", css_class="data-value")
            v.set_hexpand(True)
            v.set_xalign(1.0)
            row.append(v)
            row.set_visible(False)
            box.append(row)

            bar = Gtk.ProgressBar()
            bar.set_fraction(0.0)
            bar.add_css_class("pp-rank-bar")
            bar.set_show_text(False)
            bar.set_size_request(40, 3)
            bar.set_hexpand(True)
            bar_wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            bar_wrap.add_css_class("pp-rank-bar-row")
            bar_wrap.append(bar)
            bar_wrap.set_visible(False)
            box.append(bar_wrap)

            self._rank_rows[capi_key] = (row, v, bar, bar_wrap)

        # Engineer ranks section (dynamic rows built in refresh)
        eng_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        eng_sep.set_margin_top(6)
        box.append(eng_sep)
        self._eng_hdr = Gtk.Label(label="ENGINEERS")
        self._eng_hdr.add_css_class("data-key")
        self._eng_hdr.set_xalign(0.0)
        self._eng_hdr.set_margin_top(4)
        self._eng_hdr.set_margin_bottom(2)
        self._eng_hdr.set_visible(False)
        box.append(self._eng_hdr)
        self._eng_none_lbl = Gtk.Label(label="No engineers unlocked yet")
        self._eng_none_lbl.add_css_class("data-key")
        self._eng_none_lbl.set_xalign(0.5)
        self._eng_none_lbl.set_margin_top(4)
        box.append(self._eng_none_lbl)
        self._eng_rows: dict = {}   # name -> (row_box, val_lbl, bar, bar_wrap)
        self._eng_box  = box

        return scroll

    # ── Rep tab ────────────────────────────────────────────────────────────────

    def _build_rep_tab(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("mat-tab-scroll")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.set_margin_top(4)
        box.set_margin_end(12)   # clear GTK4 overlay scrollbar track
        scroll.set_child(box)

        self._no_rep_lbl = Gtk.Label(label="Awaiting login data…")
        self._no_rep_lbl.add_css_class("data-key")
        self._no_rep_lbl.set_xalign(0.5)
        self._no_rep_lbl.set_margin_top(8)
        box.append(self._no_rep_lbl)

        # ── Major factions ────────────────────────────────────────────────────
        major_hdr = Gtk.Label(label="MAJOR FACTIONS")
        major_hdr.add_css_class("section-sub-header")
        major_hdr.set_xalign(0.0)
        major_hdr.set_margin_top(4)
        major_hdr.set_margin_bottom(2)
        box.append(major_hdr)
        self._major_hdr = major_hdr

        self._rep_rows: dict[str, Gtk.Label] = {}
        for faction in ("Federation", "Empire", "Alliance", "Independent"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row.add_css_class("data-row")
            k = self.make_label(faction, css_class="data-key")
            k.set_hexpand(False)
            row.append(k)
            v = self.make_label("—", css_class="data-value")
            v.set_hexpand(True)
            v.set_xalign(1.0)
            row.append(v)
            row.set_visible(False)
            box.append(row)
            self._rep_rows[faction] = v

        # ── Minor factions (current system, populated from FSDJump/Location) ──
        minor_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        minor_sep.add_css_class("vitals-sep")
        minor_sep.set_margin_top(4)
        box.append(minor_sep)
        self._minor_sep = minor_sep

        minor_hdr = Gtk.Label(label="LOCAL FACTIONS")
        minor_hdr.add_css_class("section-sub-header")
        minor_hdr.set_xalign(0.0)
        minor_hdr.set_margin_top(2)
        minor_hdr.set_margin_bottom(2)
        box.append(minor_hdr)
        self._minor_hdr = minor_hdr

        self._minor_none_lbl = Gtk.Label(label="Jump to a system to see local standings")
        self._minor_none_lbl.add_css_class("data-key")
        self._minor_none_lbl.set_xalign(0.5)
        self._minor_none_lbl.set_wrap(True)
        self._minor_none_lbl.set_margin_top(4)
        box.append(self._minor_none_lbl)

        # Minor faction rows are built dynamically in refresh()
        self._minor_rep_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._minor_rep_box.set_visible(False)
        box.append(self._minor_rep_box)
        self._minor_rep_rows: dict[str, Gtk.Label] = {}

        return scroll

    # ── Tab switching ──────────────────────────────────────────────────────────

    def _on_tab_click(self, _btn, cat: str) -> None:
        self._set_active_tab(cat)

    def _set_active_tab(self, cat: str) -> None:
        self._active_tab = cat
        self._tab_stack.set_visible_child_name(cat)
        for key, btn in self._tab_btns.items():
            if key == cat:
                btn.add_css_class("mat-tab-active")
            else:
                btn.remove_css_class("mat-tab-active")

    def on_resize(self, w: int, h: int) -> None:
        super().on_resize(w, h)

    # ── Refresh ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        s = self.state

        # ── Header ────────────────────────────────────────────────────────────
        sq_rank = getattr(s, "pilot_squadron_rank", "")
        sq_name = getattr(s, "pilot_squadron_name", "")
        sq_tag  = getattr(s, "pilot_squadron_tag",  "")

        if s.pilot_name:
            # Line 1: full caps — "CMDR NAME — SQUADRON RANK"
            if sq_rank:
                lbl = f"CMDR {s.pilot_name}  —  {sq_rank.upper()}"
            elif s.cmdr_in_slf:
                lbl = f"CMDR {s.pilot_name}  [IN FIGHTER]"
            elif getattr(s, "vessel_mode", "ship") == "on_foot":
                lbl = f"CMDR {s.pilot_name}  [ON FOOT]"
            elif getattr(s, "vessel_mode", "ship") == "srv":
                lbl = f"CMDR {s.pilot_name}  [IN SRV]"
            else:
                lbl = f"CMDR {s.pilot_name}"
            self._cmdr_header_lbl.set_label(lbl)
        else:
            self._cmdr_header_lbl.set_label("COMMANDER")
        # Right side of header line 1 and line 2 depend on vehicle mode
        vessel_mode  = getattr(s, "vessel_mode",  "ship")
        srv_type     = getattr(s, "srv_type",     "")
        suit_name    = getattr(s, "suit_name",    "")
        suit_loadout = getattr(s, "suit_loadout", "")

        if vessel_mode == "on_foot":
            self._cmdr_ship_type_hdr.set_label(suit_name.upper() if suit_name else "ON FOOT")
            ident_str = suit_loadout.upper() if suit_loadout else ""
        elif vessel_mode == "srv":
            self._cmdr_ship_type_hdr.set_label(srv_type.upper() if srv_type else "SRV")
            ident_str = ""
        else:
            self._cmdr_ship_type_hdr.set_label((s.pilot_ship or "").upper())
            parts = [p for p in [s.ship_name, s.ship_ident] if p]
            ident_str = " | ".join(parts)

        if ident_str:
            self._cmdr_ship_ident_hdr.set_label(ident_str)
            self._cmdr_ship_ident_hdr.set_visible(True)
        else:
            self._cmdr_ship_ident_hdr.set_visible(False)

        # Line 2 visibility: show if squadron or ship ident is present
        if sq_name:
            tag_str = f"  [{sq_tag.upper()}]" if sq_tag else ""
            self._cmdr_squadron_lbl.set_label(f"{sq_name.upper()}{tag_str}")
            self._cmdr_squadron_lbl.set_visible(True)
        else:
            self._cmdr_squadron_lbl.set_visible(False)
        # Show line2 box if either child is visible
        self._hdr_line2.set_visible(
            self._cmdr_squadron_lbl.get_visible() or
            self._cmdr_ship_ident_hdr.get_visible()
        )

        # ── Info tab: Mode ────────────────────────────────────────────────────
        self._cmdr_mode.set_label(s.pilot_mode or "—")

        # ── Info tab: System ──────────────────────────────────────────────────
        if s.pilot_system:
            self._cmdr_system.set_label(s.pilot_system)
            self._cmdr_system.get_parent().set_visible(True)
        else:
            self._cmdr_system.set_label("—")
            self._cmdr_system.get_parent().set_visible(False)

        # ── Info tab: Body ────────────────────────────────────────────────────
        if s.pilot_body:
            body_str = s.pilot_body
            if s.pilot_system and body_str.startswith(s.pilot_system):
                body_str = body_str[len(s.pilot_system):].lstrip()
            self._cmdr_location.set_label(body_str or "—")
            self._cmdr_location.get_parent().set_visible(True)
        else:
            self._cmdr_location.set_label("—")
            self._cmdr_location.get_parent().set_visible(False)

        # ── Info tab: Fuel ────────────────────────────────────────────────────
        fuel_current = s.fuel_current
        fuel_tank    = s.fuel_tank_size
        if fuel_current is not None and fuel_tank and fuel_tank > 0:
            fuel_pct = fuel_current / fuel_tank * 100
            fuel_str = f"{fuel_pct:.0f}%"
            burn = getattr(s, "fuel_burn_rate", None)
            if burn and burn > 0:
                secs_remain = (fuel_current / burn) * 3600
                h_rem = int(secs_remain // 3600)
                m_rem = int((secs_remain % 3600) // 60)
                if h_rem > 0:
                    fuel_str += f"  (~{h_rem}h {m_rem}m)"
                else:
                    fuel_str += f"  (~{m_rem}m)"
            self._cmdr_fuel.set_label(fuel_str)
            self._cmdr_fuel.get_parent().set_visible(True)
            from core.state import FUEL_CRIT_THRESHOLD, FUEL_WARN_THRESHOLD
            for cls in ("health-good", "health-warn", "health-crit"):
                self._cmdr_fuel.remove_css_class(cls)
            if fuel_current < fuel_tank * FUEL_CRIT_THRESHOLD:
                self._cmdr_fuel.add_css_class("health-crit")
            elif fuel_current < fuel_tank * FUEL_WARN_THRESHOLD:
                self._cmdr_fuel.add_css_class("health-warn")
            else:
                self._cmdr_fuel.add_css_class("health-good")
        else:
            self._cmdr_fuel.get_parent().set_visible(False)

        # ── Info tab: Powerplay ───────────────────────────────────────────────
        has_power = bool(s.pp_power)
        self._cmdr_pp.get_parent().set_visible(has_power)
        self._cmdr_pprank.get_parent().set_visible(has_power)
        self._cmdr_pp.set_label(s.pp_power or "—")

        if s.pp_rank:
            merits = s.pp_merits_total
            if merits is not None:
                fraction, earned, span, next_rank = pp_rank_progress(s.pp_rank, merits)
                pct     = int(fraction * 100)
                pp_lbl  = f"Rank {s.pp_rank}  {pct}%"
                tooltip = (
                    f"{earned:,} / {span:,} merits to Rank {next_rank} "
                    f"({span - earned:,} remaining)"
                )
            else:
                pp_lbl   = f"Rank {s.pp_rank}"
                fraction = 0.0
                tooltip  = "Earn merits to populate progress"
            self._cmdr_pprank.set_label(pp_lbl)
            self._pp_rank_bar.set_fraction(fraction)
            self._pp_rank_bar.set_tooltip_text(tooltip)
            self._pp_rank_bar.set_visible(True)
        else:
            self._cmdr_pprank.set_label("—")
            self._pp_rank_bar.set_fraction(0.0)
            self._pp_rank_bar.set_visible(False)

        # ── Info tab: Shields / Hull — context-aware ─────────────────────────
        vm = getattr(s, "vessel_mode", "ship")

        # Update Shields label
        for cls in ("health-good", "health-warn", "health-crit"):
            self._cmdr_shields.remove_css_class(cls)
        if vm == "on_foot":
            suit_up = getattr(s, "suit_shields", True)
            self._cmdr_shields.set_label("Up" if suit_up else "Down")
            self._cmdr_shields.add_css_class("health-good" if suit_up else "health-crit")
        elif vm == "srv":
            # SRVs have no shields
            self._cmdr_shields.set_label("—")
        else:
            shield_str = fmt_shield(s.ship_shields, s.ship_shields_recharging)
            self._cmdr_shields.set_label(shield_str)
            if s.ship_shields is None:
                pass
            elif not s.ship_shields:
                self._cmdr_shields.add_css_class(
                    "health-warn" if s.ship_shields_recharging else "health-crit"
                )
            else:
                self._cmdr_shields.add_css_class("health-good")

        # Update Hull label — show SRV hull when in SRV, hide when on foot
        for cls in ("health-good", "health-warn", "health-crit"):
            self._cmdr_hull.remove_css_class(cls)
        if vm == "on_foot":
            # On-foot health not available from journal alone
            self._cmdr_hull.set_label("—")
        elif vm == "srv":
            hull_pct = getattr(s, "srv_hull", 100)
            self._cmdr_hull.set_label(f"{hull_pct}%")
            self._cmdr_hull.add_css_class(hull_css(hull_pct))
        else:
            hull_pct = s.ship_hull
            self._cmdr_hull.set_label(f"{hull_pct}%" if hull_pct is not None else "—")
            if hull_pct is not None:
                self._cmdr_hull.add_css_class(hull_css(hull_pct))

        # Update hull row label text to match context
        hull_row_key = self._cmdr_hull.get_parent().get_first_child()
        if hull_row_key:
            hull_row_key.set_label("Health" if vm == "on_foot" else "Hull")

        # ── Ranks tab ─────────────────────────────────────────────────────────
        capi_ranks    = getattr(s, "capi_ranks",    None)
        capi_progress = getattr(s, "capi_progress", None)
        has_ranks = bool(capi_ranks)
        self._no_ranks_lbl.set_visible(not has_ranks)

        if has_ranks:
            from core.state import CAPI_RANK_SKILLS
            for capi_key, _display, table in CAPI_RANK_SKILLS:
                row, v_lbl, bar, bar_wrap = self._rank_rows[capi_key]
                idx = capi_ranks.get(capi_key)
                if idx is None:
                    row.set_visible(False)
                    bar_wrap.set_visible(False)
                    continue
                rank_name = table[idx] if 0 <= idx < len(table) else str(idx)
                prog      = (capi_progress or {}).get(capi_key)
                pct_str   = f" +{prog}%" if prog is not None else ""
                v_lbl.set_label(f"{rank_name}{pct_str}")
                row.set_visible(True)
                if prog is not None:
                    bar.set_fraction(min(prog / 100.0, 1.0))
                    bar_wrap.set_visible(True)
                else:
                    bar_wrap.set_visible(False)

        # ── Rep tab ───────────────────────────────────────────────────────────
        # Engineer ranks (from CAPI capi_engineer_ranks)
        # Journal EngineerProgress (pilot_engineer_ranks) is primary — fires at every
        # login with full data. Fall back to CAPI if journal hasn't fired yet.
        eng_data = getattr(s, "pilot_engineer_ranks", None) or \
                   getattr(s, "capi_engineer_ranks", None) or []
        unlocked = [e for e in eng_data if e.get("unlocked")]
        self._eng_hdr.set_visible(bool(unlocked))
        self._eng_none_lbl.set_visible(not bool(unlocked))
        seen_eng: set = set()
        for eng in sorted(unlocked, key=lambda e: (-(e.get("rank") or 0), e.get("name", ""))):
            name = eng.get("name", "")
            if not name:
                continue
            seen_eng.add(name)
            rank    = eng.get("rank") or 0
            prog    = eng.get("progress")
            val_str = f"G{rank}" if rank else "Invited"
            if prog is not None and rank < 5:
                val_str += f" +{prog}%"
            if name not in self._eng_rows:
                erow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                erow.add_css_class("data-row")
                ek = self.make_label(name, css_class="data-key")
                ek.set_hexpand(False)
                erow.append(ek)
                evl = self.make_label("—", css_class="data-value")
                evl.set_hexpand(True)
                evl.set_xalign(1.0)
                erow.append(evl)
                ebar = Gtk.ProgressBar()
                ebar.set_fraction(0.0)
                ebar.add_css_class("pp-rank-bar")
                ebar.set_show_text(False)
                ebar.set_size_request(40, 3)
                ebar.set_hexpand(True)
                ebw = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                ebw.add_css_class("pp-rank-bar-row")
                ebw.append(ebar)
                ebw.set_visible(False)
                self._eng_box.append(erow)
                self._eng_box.append(ebw)
                self._eng_rows[name] = (erow, evl, ebar, ebw)
            _, evl, ebar, ebw = self._eng_rows[name]
            evl.set_label(val_str)
            if prog is not None and rank < 5:
                ebar.set_fraction(min(prog / 100.0, 1.0))
                ebw.set_visible(True)
            else:
                ebw.set_visible(False)
        for name, (erow, _evl, _eb, ebw) in self._eng_rows.items():
            erow.set_visible(name in seen_eng)
            if name not in seen_eng:
                ebw.set_visible(False)

    # Major faction standing: Journal Reputation event is primary;
        # fall back to capi_reputation when journal not yet available.
        pilot_rep = getattr(s, "pilot_reputation", None) or {}
        if not pilot_rep:
            _capi_rep = getattr(s, "capi_reputation", None) or {}
            pilot_rep = {k.title(): v for k, v in _capi_rep.items()}
        has_rep   = bool(pilot_rep)
        self._no_rep_lbl.set_visible(not has_rep)
        self._major_hdr.set_visible(has_rep)
        self._minor_sep.set_visible(has_rep)
        self._minor_hdr.set_visible(has_rep)

        for faction, v_lbl in self._rep_rows.items():
            val = (pilot_rep or {}).get(faction)
            if val is not None:
                v_lbl.set_label(f"{val:.1f}%")
                v_lbl.get_parent().set_visible(True)
            else:
                v_lbl.get_parent().set_visible(False)

        # Minor/local faction standing: FSDJump/Location Factions[].MyReputation
        minor_rep = getattr(s, "pilot_minor_reputation", None)
        if minor_rep:
            self._minor_none_lbl.set_visible(False)
            self._minor_rep_box.set_visible(True)
            seen = set()
            for name, val in sorted(minor_rep.items(), key=lambda kv: -kv[1]):
                seen.add(name)
                if name not in self._minor_rep_rows:
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                    row.add_css_class("data-row")
                    k = self.make_label(name, css_class="data-key")
                    k.set_hexpand(False)
                    row.append(k)
                    v = self.make_label("—", css_class="data-value")
                    v.set_hexpand(True)
                    v.set_xalign(1.0)
                    row.append(v)
                    self._minor_rep_box.append(row)
                    self._minor_rep_rows[name] = v
                self._minor_rep_rows[name].set_label(f"{val:.1f}%")
            # Hide rows for factions no longer in current system
            for name, v_lbl in self._minor_rep_rows.items():
                v_lbl.get_parent().set_visible(name in seen)
        else:
            self._minor_none_lbl.set_visible(has_rep)
            self._minor_rep_box.set_visible(False)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Zero all progress bars before window teardown — prevents GTK gizmo warning."""
        if hasattr(self, "_pp_rank_bar"):
            self._pp_rank_bar.set_fraction(0.0)
            self._pp_rank_bar.set_visible(False)
        if hasattr(self, "_rank_rows"):
            for _row, _lbl, bar, bar_wrap in self._rank_rows.values():
                bar.set_fraction(0.0)
                bar_wrap.set_visible(False)
        if hasattr(self, "_eng_rows"):
            for _row, _lbl, bar, bar_wrap in self._eng_rows.values():
                bar.set_fraction(0.0)
                bar_wrap.set_visible(False)
