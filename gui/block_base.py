"""
gui/block_base.py — BlockWidget base class for all dashboard blocks.

Every builtin block (commander, missions, session_stats, crew_slf, alerts)
subclasses BlockWidget.  The base class provides:

  - Standard section construction via make_section / make_row
  - A consistent build() / refresh() contract
  - Access to core (state, active_session, cfg, emitter, fmt_* helpers)
  - Optional visibility control (set_visible)

Subclass contract:
  - Override build(parent: Gtk.Box) -> None   — add widgets to parent
  - Override refresh() -> None                — update widget labels from state
  - Set BLOCK_TITLE: str                       — section header text
  - Set BLOCK_CSS: str                         — CSS class on the root section box

The base never calls build() or refresh() itself; EdmdWindow drives both.
"""

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError:
    raise ImportError(
        "PyGObject not found.\n"
        "  Arch/Manjaro:  pacman -S python-gobject gtk4\n"
        "  pip:           pip install PyGObject"
    )

from gui.helpers import make_label, make_section, make_row


class BlockWidget:
    """Base class for all EDMD dashboard blocks.

    Parameters
    ----------
    core : CoreAPI
        Passed in by EdmdWindow; provides state, active_session,
        cfg, emitter, fmt_credits, fmt_duration, rate_per_hour.
    """

    BLOCK_TITLE: str = ""
    BLOCK_CSS:   str = "block"

    def __init__(self, core):
        self.core    = core
        self.state   = core.state
        self.session = core.active_session
        self._root: Gtk.Box | None = None   # set by _build_section()

    # ── Section scaffolding ───────────────────────────────────────────────────

    def _build_section(
        self,
        parent: Gtk.Box,
        title: str | None = None,
        title_widget: Gtk.Widget | None = None,
    ) -> Gtk.Box:
        """Create the standard panel section and append it to parent.

        Returns the inner body Box for appending data rows.
        Stores the outer section Box as self._root.
        """
        t = title if title is not None else self.BLOCK_TITLE
        outer, inner = make_section(t, title_widget=title_widget)
        outer.add_css_class(self.BLOCK_CSS)
        parent.append(outer)
        self._root = outer
        return inner

    # ── Visibility ────────────────────────────────────────────────────────────

    def set_visible(self, visible: bool) -> None:
        """Show or hide the entire block."""
        if self._root is not None:
            self._root.set_visible(visible)

    def is_visible(self) -> bool:
        if self._root is None:
            return False
        return self._root.get_visible()

    # ── Convenience re-exports ────────────────────────────────────────────────
    # Subclasses call self.make_row(...) etc. rather than importing separately.

    @staticmethod
    def make_label(text: str = "", css_class=None, xalign: float = 0.0) -> Gtk.Label:
        return make_label(text, css_class=css_class, xalign=xalign)

    @staticmethod
    def make_row(label_text: str, value_text: str = "—") -> tuple:
        return make_row(label_text, value_text)

    @staticmethod
    def make_section(title: str, title_widget=None) -> tuple:
        return make_section(title, title_widget=title_widget)

    # ── Formatting helpers (delegated to core) ─────────────────────────────────

    def fmt_credits(self, n) -> str:
        return self.core.fmt_credits(n)

    def fmt_duration(self, s) -> str:
        return self.core.fmt_duration(s)

    def rate_per_hour(self, s, precision=None) -> float:
        return self.core.rate_per_hour(s, precision)

    # ── Subclass interface ────────────────────────────────────────────────────

    def build(self, parent: Gtk.Box) -> None:
        """Build all widgets and append the root section to parent.

        Must call self._build_section(parent, ...) to create self._root.
        Subclasses override this.
        """
        self._build_section(parent)

    def refresh(self) -> None:
        """Read from self.state / self.session and update all widget labels.

        Called by EdmdWindow on GLib.timeout_add(1000, ...) and on
        targeted gui_queue messages.  Must be safe to call at any time.
        Subclasses override this.
        """
