"""
gui/blocks/cargo.py — Cargo hold inventory block.

One Gtk.Grid contains ALL rows — headers, category headers, item rows, totals.
This is the only way to guarantee pixel-perfect column alignment in GTK4:
every cell in the same column index is allocated identical width by the Grid.

Column indices:
  0  name     hexpand
  1  qty      fixed _W_QTY  + margin_end _M_QTY
  2  sell     fixed _W_SELL
  3  avg      fixed _W_AVG

Row layout (inside grid):
  row 0   blank | blank        | StationName (xalign=0.5) | "Gal. Avg"
  row 1   Item  | Qty.         | Sell                     | blank
  row 2   ──────separator (colspan 4)──────────────────────────────────
  row 3+  category / item / totals rows appended dynamically
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Pango
except ImportError:
    raise ImportError("PyGObject / GTK4 not found.")

from gui.block_base import BlockWidget

_W_QTY  = 46   # qty column width
_W_SELL = 82   # sell price column width
_W_AVG  = 82   # avg price column width
_M_QTY  = 8    # extra right-margin on qty column (visual separation from sell)


def _fmt_cr(val: int | float) -> str:
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.0f}K"
    return f"{int(val):,}"


def _lbl(text: str, xalign: float = 0.0, css: str = "data-value",
         hexpand: bool = False, width: int = -1,
         margin_end: int = 0, ellipsize: bool = False) -> Gtk.Label:
    """Uniform label factory."""
    l = Gtk.Label(label=text)
    l.set_xalign(xalign)
    l.add_css_class(css)
    l.set_hexpand(hexpand)
    if width > 0:
        l.set_size_request(width, -1)
    if margin_end:
        l.set_margin_end(margin_end)
    if ellipsize:
        l.set_ellipsize(Pango.EllipsizeMode.END)
    return l


class CargoBlock(BlockWidget):
    BLOCK_TITLE = "CARGO"
    BLOCK_CSS   = "cargo-block"

    # Next grid row available for dynamic content
    _FIRST_DATA_ROW = 3

    def build(self, parent: Gtk.Box) -> None:
        # ── Block header ─────────────────────────────────────────────────────
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._cargo_title = Gtk.Label(label="CARGO")
        self._cargo_title.set_xalign(0.0)
        self._cargo_title.set_hexpand(True)
        hdr_box.append(self._cargo_title)
        self._cargo_usage = Gtk.Label(label="")
        self._cargo_usage.set_xalign(1.0)
        self._cargo_usage.add_css_class("data-key")
        hdr_box.append(self._cargo_usage)

        body = self._build_section(parent, title_widget=hdr_box)

        # ── Single grid for everything ────────────────────────────────────────
        # Wrap in ScrolledWindow so the grid can scroll when cargo is large.
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("mat-tab-scroll")
        body.append(scroll)

        self._grid = Gtk.Grid()
        self._grid.set_column_spacing(4)
        self._grid.set_row_spacing(0)
        self._grid.set_margin_start(4)
        self._grid.set_margin_end(12)
        self._grid.set_hexpand(True)
        scroll.set_child(self._grid)

        # ── Grid row 0: station name / Gal. Avg ──────────────────────────────
        self._mkt_visible = False
        _r0c0 = _lbl("", hexpand=True)
        _r0c1 = _lbl("", css="data-key", width=_W_QTY, margin_end=_M_QTY)
        self._mkt_loc_lbl = _lbl("", xalign=0.5, css="data-key",
                                  width=_W_SELL, ellipsize=True)
        _r0c3 = _lbl("Gal. Avg", xalign=1.0, css="data-key", width=_W_AVG)
        self._grid.attach(_r0c0, 0, 0, 1, 1)
        self._grid.attach(_r0c1, 1, 0, 1, 1)
        self._grid.attach(self._mkt_loc_lbl, 2, 0, 1, 1)
        self._grid.attach(_r0c3, 3, 0, 1, 1)

        # ── Grid row 1: column labels ─────────────────────────────────────────
        _r1c0 = _lbl("Item",  css="data-key", hexpand=True)
        _r1c1 = _lbl("Qty.", xalign=1.0, css="data-key",
                      width=_W_QTY, margin_end=_M_QTY)
        _r1c2 = _lbl("Sell", xalign=1.0, css="data-key", width=_W_SELL)
        _r1c3 = _lbl("",     xalign=1.0, css="data-key", width=_W_AVG)
        self._grid.attach(_r1c0, 0, 1, 1, 1)
        self._grid.attach(_r1c1, 1, 1, 1, 1)
        self._grid.attach(_r1c2, 2, 1, 1, 1)
        self._grid.attach(_r1c3, 3, 1, 1, 1)

        # ── Grid row 2: separator ─────────────────────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._grid.attach(sep, 0, 2, 4, 1)

        # Empty label (shown when hold is empty)
        self._empty_lbl = _lbl("— empty —", xalign=0.5, css="data-key",
                                 hexpand=True)
        self._grid.attach(self._empty_lbl, 0, self._FIRST_DATA_ROW, 4, 1)
        self._empty_lbl.set_visible(True)

        # Row tracker: key → grid_row_index
        self._item_grid_rows: dict = {}   # cargo key  → row int
        self._cat_grid_rows:  dict = {}   # category   → row int
        self._totals_row:     int  = -1
        self._next_row:       int  = self._FIRST_DATA_ROW + 1

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        s           = self.state
        items       = getattr(s, "cargo_items",       {})
        cap         = getattr(s, "cargo_capacity",    0)
        mkt_info    = getattr(s, "cargo_market_info", {})
        commodities = mkt_info.get("commodities", {})

        used = sum(v["count"] for v in items.values())

        # ── Capacity header ───────────────────────────────────────────────────
        if cap > 0:
            self._cargo_usage.set_label(f"{used} / {cap} t")
        elif used > 0:
            self._cargo_usage.set_label(f"{used} t")
        else:
            self._cargo_usage.set_label("")
        for cls in ("cargo-full", "cargo-warn", "cargo-ok"):
            self._cargo_usage.remove_css_class(cls)
        if cap > 0:
            pct = used / cap
            if pct >= 1.0:    self._cargo_usage.add_css_class("cargo-full")
            elif pct >= 0.75: self._cargo_usage.add_css_class("cargo-warn")
            else:              self._cargo_usage.add_css_class("cargo-ok")

        # ── Station / market header row ───────────────────────────────────────
        stn  = mkt_info.get("station_name", "")
        sys_ = mkt_info.get("star_system",  "")
        if stn or sys_:
            loc = f"{stn} | {sys_}" if (stn and sys_) else stn or sys_
            self._mkt_loc_lbl.set_label(loc)
        else:
            self._mkt_loc_lbl.set_label("")

        # ── Full re-render of data rows ───────────────────────────────────────
        self._clear_data_rows()

        if not items:
            self._empty_lbl.set_visible(True)
            return
        self._empty_lbl.set_visible(False)

        # Enrich with market data and sort category → name
        enriched = []
        for key, data in items.items():
            mkt = commodities.get(key, {})
            enriched.append({
                "key":        key,
                "name":       mkt.get("name_local") or data["name_local"],
                "category":   mkt.get("category_local", "Uncategorised"),
                "count":      data["count"],
                "stolen":     data.get("stolen", False),
                "sell_price": mkt.get("sell_price", 0),
                "mean_price": mkt.get("mean_price", 0),
            })
        enriched.sort(key=lambda x: (x["category"].lower(), x["name"].lower()))

        row = self._FIRST_DATA_ROW
        current_cat = None
        total_sell = total_avg = 0

        for item in enriched:
            cat = item["category"]
            if cat != current_cat:
                current_cat = cat
                cat_lbl = _lbl(cat.upper(), css="data-key", hexpand=True)
                cat_lbl.set_margin_top(4)
                self._grid.attach(cat_lbl,                      0, row, 1, 1)
                self._grid.attach(_lbl("", css="data-key", width=_W_QTY, margin_end=_M_QTY), 1, row, 1, 1)
                self._grid.attach(_lbl("", css="data-key", width=_W_SELL),                   2, row, 1, 1)
                self._grid.attach(_lbl("", css="data-key", width=_W_AVG),                    3, row, 1, 1)
                self._cat_grid_rows[cat] = row
                row += 1

            count = item["count"]
            sell  = item["sell_price"]
            avg   = item["mean_price"]
            total_sell += sell * count
            total_avg  += avg  * count

            name_str = ("⚠ " if item["stolen"] else "") + item["name"]
            n_lbl = _lbl(name_str, css="data-value", hexpand=True, ellipsize=True)
            if item["stolen"]:
                n_lbl.add_css_class("cargo-stolen")
            n_lbl.set_margin_start(12)

            self._grid.attach(n_lbl,
                              0, row, 1, 1)
            self._grid.attach(_lbl(f"{count} t", xalign=1.0, css="data-key",
                                    width=_W_QTY, margin_end=_M_QTY),
                              1, row, 1, 1)
            self._grid.attach(_lbl(_fmt_cr(sell) if sell else "—",
                                    xalign=1.0, css="data-key", width=_W_SELL),
                              2, row, 1, 1)
            self._grid.attach(_lbl(_fmt_cr(avg) if avg else "—",
                                    xalign=1.0, css="data-key", width=_W_AVG),
                              3, row, 1, 1)
            self._item_grid_rows[item["key"]] = row
            row += 1

        # ── Totals ────────────────────────────────────────────────────────────
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(8)
        self._grid.attach(sep2, 0, row, 4, 1)
        row += 1

        self._grid.attach(_lbl("Totals", css="data-key", hexpand=True),
                          0, row, 1, 1)
        self._grid.attach(_lbl(f"{used} t", xalign=1.0, css="data-key",
                                width=_W_QTY, margin_end=_M_QTY),
                          1, row, 1, 1)
        self._grid.attach(_lbl(_fmt_cr(total_sell) if total_sell else "—",
                                xalign=1.0, css="data-key", width=_W_SELL),
                          2, row, 1, 1)
        self._grid.attach(_lbl(_fmt_cr(total_avg) if total_avg else "—",
                                xalign=1.0, css="data-key", width=_W_AVG),
                          3, row, 1, 1)
        self._totals_row = row

    def _clear_data_rows(self) -> None:
        """Remove all dynamically-added rows from the grid."""
        for row_idx in set(self._item_grid_rows.values()) | \
                       set(self._cat_grid_rows.values()):
            for col in range(4):
                child = self._grid.get_child_at(col, row_idx)
                if child:
                    self._grid.remove(child)
        self._item_grid_rows.clear()
        self._cat_grid_rows.clear()

        if self._totals_row >= 0:
            # Remove separator row above totals and totals row itself
            for r in (self._totals_row - 1, self._totals_row):
                for col in range(4):
                    child = self._grid.get_child_at(col, r)
                    if child:
                        self._grid.remove(child)
            self._totals_row = -1
