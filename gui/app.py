"""
gui/app.py — GTK4 application window for Elite Dangerous Monitor Daemon.

Architecture:
  - Monitor runs on a background thread (run_monitor in core/journal.py)
  - GUI runs on the GTK main thread
  - Communication via thread-safe queue: gui_queue
  - GLib.idle_add / timeout_add polls the queue and updates widgets safely

Replaces edmd_gui.py.  Wired to CoreAPI instead of raw state arguments.
"""

import signal
from pathlib import Path

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk
except ImportError:
    raise ImportError(
        "PyGObject not found.\n"
        "  Arch/Manjaro:  pacman -S python-gobject gtk4\n"
        "  pip:           pip install PyGObject"
    )

from gui.helpers import apply_theme, avatar_path_for_theme, make_label
from gui.blocks  import (
    CommanderBlock,
    CrewSlfBlock,
    MissionsBlock,
    SessionStatsBlock,
    AlertsBlock,
)

# WM_CLASS set before the application starts so i3 and other EWMH WMs can
# match on it.  WM_CLASS will be ("edmd", "EDMD").
GLib.set_prgname("edmd")
GLib.set_application_name("EDMD")


class EdmdWindow(Gtk.ApplicationWindow):

    POLL_MS  = 100    # gui_queue poll interval (ms)
    TICK_MS  = 1000   # stats / crew / missions refresh interval (ms)

    def __init__(self, app, core, program: str, version: str):
        super().__init__(application=app, title=f"{program} v{version}")
        self.set_title(f"{program} v{version}")

        self._core    = core
        self._program = program
        self._version = version

        self.set_default_size(1280, 720)
        self.add_css_class("edmd-window")

        self._build_ui()
        self._refresh_all()

        GLib.timeout_add(self.POLL_MS,  self._poll_queue)
        GLib.timeout_add(self.TICK_MS,  self._tick)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        program = self._program
        version = self._version

        # ── Header bar ────────────────────────────────────────────────────────
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        header.add_css_class("edmd-header")

        title_lbl = Gtk.Label(label=f"{program}  v{version}")
        title_lbl.add_css_class("header-title")
        header.pack_start(title_lbl)
        header.set_title_widget(Gtk.Box())   # suppress built-in centre title

        self._fs_button = Gtk.Button()
        self._fs_button.set_icon_name("view-fullscreen-symbolic")
        self._fs_button.set_tooltip_text("Toggle fullscreen (F11)")
        self._fs_button.connect("clicked", self._toggle_fullscreen)
        self._fs_button.add_css_class("flat")
        header.pack_end(self._fs_button)

        self.set_titlebar(header)
        self._is_fullscreen = False

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        # ── Root layout: log (left) + panel scroll (right) ────────────────────
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root.add_css_class("root-box")
        self.set_child(root)

        # ── Event log ─────────────────────────────────────────────────────────
        log_frame = Gtk.Frame()
        log_frame.add_css_class("log-frame")
        log_frame.set_hexpand(True)
        log_frame.set_vexpand(True)

        log_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        log_frame.set_child(log_outer)

        log_header = make_label("  Event Log", css_class="log-header")
        log_outer.append(log_header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("log-scroll")

        self._log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self._log_box.add_css_class("log-inner")
        self._log_box.set_valign(Gtk.Align.END)
        scroll.set_child(self._log_box)
        log_outer.append(scroll)
        self._log_scroll = scroll

        root.append(log_frame)

        # ── Right panel ───────────────────────────────────────────────────────
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.add_css_class("right-panel")
        panel.set_vexpand(True)

        panel_scroll = Gtk.ScrolledWindow()
        panel_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        panel_scroll.set_vexpand(True)
        panel_scroll.set_size_request(340, -1)
        panel_scroll.set_hexpand(False)
        panel_scroll.set_child(panel)
        panel_scroll.add_css_class("panel-scroll")

        root.append(panel_scroll)

        # ── Build blocks ──────────────────────────────────────────────────────
        self._block_cmdr   = CommanderBlock(self._core)
        self._block_crew   = CrewSlfBlock(self._core)
        self._block_miss   = MissionsBlock(self._core)
        self._block_stats  = SessionStatsBlock(self._core)
        self._block_alerts = AlertsBlock(self._core)

        self._block_cmdr.build(panel)
        self._block_crew.build(panel)
        self._block_miss.build(panel)
        self._block_stats.build(panel)
        self._build_sponsor_panel(panel)
        self._block_alerts.build(panel)

    def _build_sponsor_panel(self, parent: Gtk.Box) -> None:
        """Avatar mark + Ko-Fi / PayPal / GitHub link row."""
        theme = self._core.cfg.gui_cfg.get("Theme", "default")

        avatar = avatar_path_for_theme(theme)
        if avatar:
            avatar_pic = Gtk.Picture.new_for_filename(str(avatar))
            avatar_pic.set_can_shrink(True)
            avatar_pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            avatar_pic.set_size_request(72, 72)
            avatar_pic.set_opacity(0.55)
            avatar_pic.set_halign(Gtk.Align.CENTER)
            avatar_pic.set_margin_top(4)
            avatar_pic.set_margin_bottom(2)
            parent.append(avatar_pic)

        from gui.helpers import make_section
        section, body = make_section("Sponsoring Development")
        section.set_vexpand(True)
        section.set_valign(Gtk.Align.END)
        parent.append(section)

        link_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        link_row.add_css_class("sponsor-link-row")

        links = [
            ("☕ Ko-Fi",  "https://ko-fi.com/drworman"),
            ("💳 PayPal", "https://paypal.me/DavidWorman"),
            ("🐙 GitHub", f"https://github.com/{self._core.state.__class__.__module__.split('.')[0]}"),
        ]
        # Use the constant directly
        from core.state import GITHUB_REPO
        links[-1] = ("🐙 GitHub", f"https://github.com/{GITHUB_REPO}")

        for i, (label_text, url) in enumerate(links):
            if i > 0:
                sep = make_label(" | ", css_class="sponsor-sep")
                link_row.append(sep)
            btn = Gtk.LinkButton(uri=url, label=label_text)
            btn.set_halign(Gtk.Align.START)
            btn.add_css_class("sponsor-link")
            link_row.append(btn)
            if "github.com" in url:
                self._github_btn = btn

        body.append(link_row)

    # ── Block refresh ─────────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._block_cmdr.refresh()
        self._block_crew.refresh()
        self._block_miss.refresh()
        self._block_stats.refresh()
        self._block_alerts.refresh()

    # ── Event log ─────────────────────────────────────────────────────────────

    def _append_log(self, text: str) -> None:
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0.0)
        lbl.set_wrap(False)
        lbl.set_selectable(True)
        lbl.add_css_class("log-entry")
        self._log_box.append(lbl)
        GLib.idle_add(self._scroll_to_bottom)

        # Trim log to 2000 entries
        children = []
        child = self._log_box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()
        if len(children) > 2000:
            self._log_box.remove(children[0])

    def _scroll_to_bottom(self) -> bool:
        adj = self._log_scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False   # don't repeat

    # ── Fullscreen ────────────────────────────────────────────────────────────

    def _toggle_fullscreen(self, *_) -> None:
        if self._is_fullscreen:
            self.unfullscreen()
            self._fs_button.set_icon_name("view-fullscreen-symbolic")
            self._fs_button.set_tooltip_text("Toggle fullscreen (F11)")
            self._is_fullscreen = False
        else:
            self.fullscreen()
            self._fs_button.set_icon_name("view-restore-symbolic")
            self._fs_button.set_tooltip_text("Exit fullscreen (F11)")
            self._is_fullscreen = True

    def _on_key_pressed(self, ctrl, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_F11:
            self._toggle_fullscreen()
            return True
        return False

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll_queue(self) -> bool:
        """Drain gui_queue and dispatch targeted refreshes. Runs every POLL_MS."""
        try:
            while True:
                msg_type, payload = self._core.gui_queue.get_nowait()

                if msg_type == "log":
                    self._append_log(payload)

                elif msg_type in ("cmdr_update", "vessel_update"):
                    self._block_cmdr.refresh()

                elif msg_type == "crew_update":
                    self._block_crew.refresh()

                elif msg_type == "slf_update":
                    self._block_crew.refresh()

                elif msg_type == "mission_update":
                    self._block_miss.refresh()

                elif msg_type == "stats_update":
                    self._block_stats.refresh()

                elif msg_type == "alerts_update":
                    self._block_alerts.refresh()

                elif msg_type == "all_update":
                    self._refresh_all()

                elif msg_type == "update_notice":
                    self._show_update_notice(payload)

        except Exception:
            pass   # queue.Empty or shutdown race — normal

        return True   # keep timer running

    def _tick(self) -> bool:
        """Refresh time-sensitive blocks every second."""
        self._block_stats.refresh()
        self._block_miss.refresh()
        self._block_crew.refresh()
        self._block_alerts.refresh()
        return True

    # ── Update notice ─────────────────────────────────────────────────────────

    def _show_update_notice(self, version: str) -> None:
        """Append an Upgrade button below the GitHub link when a new version is available."""
        import sys, os
        try:
            upgrade_btn = Gtk.Button(label=f"⬆  Upgrade to v{version}")
            upgrade_btn.add_css_class("upgrade-btn")
            upgrade_btn.set_margin_top(4)
            upgrade_btn.set_tooltip_text(
                "Pull latest version from GitHub and restart EDMD automatically"
            )

            def _do_upgrade(_btn):
                try:
                    from core import save_session_state
                    s = self._core.state
                    if s.session_start_time:
                        # journal_file reference lives in run_monitor's closure;
                        # best-effort save via state persistence
                        save_session_state(Path("."), self._core.active_session)
                except Exception:
                    pass
                new_argv = [a for a in sys.argv if a != "--upgrade"] + ["--upgrade"]
                os.execv(sys.executable, [sys.executable] + new_argv)

            upgrade_btn.connect("clicked", _do_upgrade)

            link_row = self._github_btn.get_parent()
            if link_row and link_row.get_parent():
                link_row.get_parent().append(upgrade_btn)
                self._upgrade_btn = upgrade_btn

            self._github_btn.set_label(f"🐙  GitHub  (v{version} available)")
            self._github_btn.add_css_class("update-available")
        except Exception:
            pass   # update notice is informational — degrade gracefully


# ── Application ───────────────────────────────────────────────────────────────

class EdmdApp(Gtk.Application):
    """GTK Application wrapper.  Instantiate and call run(sys.argv)."""

    def __init__(self, core, program: str, version: str):
        super().__init__(application_id="com.drworman.edmd")
        self._core    = core
        self._program = program
        self._version = version
        self._theme   = core.cfg.gui_cfg.get("Theme", "default")

    def do_activate(self) -> None:
        apply_theme(self._theme)
        win = EdmdWindow(
            app=self,
            core=self._core,
            program=self._program,
            version=self._version,
        )
        win.present()

        # Handle Ctrl+C cleanly
        signal.signal(signal.SIGINT, lambda *_: self.quit())
        GLib.timeout_add(200, lambda: True)   # periodic wakeup to notice signal
