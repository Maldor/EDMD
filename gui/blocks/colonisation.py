"""
gui/blocks/colonisation.py — Colonisation construction site tracker block.

Shows active construction sites with resource requirements, delivery progress,
and remaining quantities. If docked at a construction depot, highlights the
current site and cross-references ship cargo.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget


def _pct_bar(provided: int, required: int, width: int = 12) -> str:
    """Return a simple ASCII progress bar string."""
    if required <= 0:
        return "█" * width
    filled = round(provided / required * width)
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


class ColonisationBlock(BlockWidget):
    BLOCK_TITLE = "Colonisation"
    BLOCK_CSS   = "colonisation-block"

    DEFAULT_COL    = 0
    DEFAULT_ROW    = 9
    DEFAULT_WIDTH  = 8
    DEFAULT_HEIGHT = 5

    def build(self, parent: Gtk.Box) -> None:
        body = self._build_section(parent)
        self._scroll_body = self._make_scroll_body(body)

        # Status label (docked / idle)
        self._status_label = self.make_label("No construction sites tracked", css_class="data-value")
        self._status_label.set_wrap(True)
        self._scroll_body.append(self._status_label)

        # Container rebuilt on each refresh
        self._sites_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._scroll_body.append(self._sites_box)

    def refresh(self) -> None:
        state = self.state
        sites = getattr(state, "colonisation_sites", [])
        docked = getattr(state, "colonisation_docked", False)
        current_mid = getattr(state, "_colonisation_current_market_id", None)
        cargo = getattr(state, "cargo_items", {})

        # Clear previous site rows
        child = self._sites_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._sites_box.remove(child)
            child = nxt

        active = [s for s in sites if not s.get("complete") and not s.get("failed")]
        done   = [s for s in sites if s.get("complete")]
        failed = [s for s in sites if s.get("failed")]

        if not sites:
            self._status_label.set_label("No construction sites tracked.\nDock at a construction depot to begin.")
            self._status_label.set_visible(True)
            return

        self._status_label.set_visible(False)

        for site in active:
            is_current = docked and site.get("market_id") == current_mid
            self._add_site_rows(site, cargo if is_current else {}, is_current)

        for site in done:
            lbl = self.make_label(
                f"✓ {site.get('station') or site.get('system', 'Unknown')} — complete",
                css_class="data-key"
            )
            lbl.add_css_class("status-ready")
            self._sites_box.append(lbl)

        for site in failed:
            lbl = self.make_label(
                f"✗ {site.get('station') or site.get('system', 'Unknown')} — failed",
                css_class="data-key"
            )
            lbl.add_css_class("status-alert")
            self._sites_box.append(lbl)

    def _add_site_rows(self, site: dict, cargo: dict, is_current: bool) -> None:
        """Add GTK rows for a single active construction site."""
        name = site.get("station") or site.get("system", "Unknown")
        pct  = round(site.get("progress", 0.0) * 100)

        # Site header
        header_text = f"{'▶ ' if is_current else ''}{name}  {pct}%"
        header = self.make_label(header_text, css_class="data-key")
        if is_current:
            header.add_css_class("status-active")
        self._sites_box.append(header)

        resources = site.get("resources", {})
        if not resources:
            note = self.make_label("  (dock to load requirements)", css_class="data-value")
            self._sites_box.append(note)
            return

        # Only show commodities that still need delivery
        remaining_items = [
            (key, info) for key, info in resources.items()
            if info["provided"] < info["required"]
        ]

        if not remaining_items:
            done_lbl = self.make_label("  All resources delivered!", css_class="data-value")
            done_lbl.add_css_class("status-ready")
            self._sites_box.append(done_lbl)
            return

        # Sort by most-needed first
        remaining_items.sort(key=lambda x: -(x[1]["required"] - x[1]["provided"]))

        for key, info in remaining_items:
            display   = info.get("name") or key
            required  = info["required"]
            provided  = info["provided"]
            needed    = required - provided
            in_cargo  = 0
            if cargo:
                # cargo_items keys are canonical lowercase
                in_cargo = cargo.get(key, {}).get("count", 0) if isinstance(cargo.get(key), dict) \
                           else cargo.get(key, 0)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row.add_css_class("data-row")

            name_lbl = self.make_label(f"  {display}", css_class="data-key")
            name_lbl.set_hexpand(True)
            row.append(name_lbl)

            # Needed vs provided
            need_str = f"{needed:,} needed"
            if in_cargo > 0:
                can_deliver = min(in_cargo, needed)
                need_str   += f"  ({can_deliver:,} in hold)"

            val_lbl = self.make_label(need_str, css_class="data-value")
            val_lbl.set_xalign(1.0)
            if in_cargo >= needed:
                val_lbl.add_css_class("status-ready")
            elif in_cargo > 0:
                val_lbl.add_css_class("status-active")
            row.append(val_lbl)

            self._sites_box.append(row)

        # Summary: total remaining tonnes
        total_remaining = sum(
            max(0, i["required"] - i["provided"]) for i in resources.values()
        )
        if total_remaining > 0:
            summ = self.make_label(
                f"  Total remaining: {total_remaining:,} t",
                css_class="data-value"
            )
            self._sites_box.append(summ)
