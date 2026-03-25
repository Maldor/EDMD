"""
core/emit.py — Terminal output, Discord webhook, and event emission.

Depends on: core.state, core.config
"""

import re
import queue
from datetime import datetime, timezone

try:
    from discord_webhook import DiscordEmbed, DiscordWebhook
    notify_enabled = True
except ImportError:
    notify_enabled = False
    print("Module discord_webhook unavailable: operating with terminal output only.\n")

from core.state import MAX_DUPLICATES, PATTERN_WEBHOOK


# ── Terminal colour codes ─────────────────────────────────────────────────────

class Terminal:
    CYAN  = "\033[96m"
    YELL  = "\033[93m"
    EASY  = "\x1b[38;5;157m"
    HARD  = "\x1b[38;5;217m"
    WARN  = "\x1b[38;5;215m"
    BAD   = "\x1b[38;5;15m\x1b[48;5;1m"
    GOOD  = "\x1b[38;5;15m\x1b[48;5;2m"
    WHITE = "\033[97m"
    END   = "\x1b[0m"

WARNING = f"{Terminal.WARN}Warning:{Terminal.END}"

AVATAR_URL = (
    "https://raw.githubusercontent.com/drworman/EDMD/"
    "refs/heads/main/images/edmd_avatar_512.png"
)


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_duration(seconds) -> str:
    """Format a duration in seconds to H:MM:SS (or M:SS)."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "0:00"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs    = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def fmt_credits(number) -> str:
    """Format credit values into k / M / B notation."""
    try:
        n = int(number)
    except (TypeError, ValueError):
        return "0"
    if n >= 995_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 995_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1_000:.1f}k"


def rate_per_hour(seconds: float = 0, precision=None) -> float:
    """Calculate a rate per hour from an average interval in seconds."""
    if seconds > 0:
        return round(3600 / seconds, precision)
    return 0


def clip_name(name: str, max_len: int) -> str:
    """Clip a string to max_len characters, appending '..' if truncated."""
    if len(name) <= max_len:
        return name
    return f"{name[:max_len].rstrip()}.."


# ── Emitter ───────────────────────────────────────────────────────────────────

class Emitter:
    """Owns the Discord webhook handle and all emit state.

    Instantiated once in edmd.py and passed into CoreAPI.
    """

    def __init__(
        self,
        cfg_mgr,           # ConfigManager
        state,             # MonitorState (read-only use)
        gui_queue: queue.Queue | None = None,
        notify_test: bool = False,
        gui_mode: bool = False,
    ):
        self._cfg          = cfg_mgr
        self._state        = state
        self._gui_queue    = gui_queue
        self.notify_test   = notify_test
        self.gui_mode      = gui_mode
        self._discord_hook = None
        self._discord_up   = False  # enabled after _init_webhook() succeeds

        # Deferred update notice: set True when update_notice is received;
        # sent on the first real emit() after startup.
        self._discord_update_pending = False
        self._update_version: str | None = None

        self._init_webhook()

    def _init_webhook(self) -> None:
        global notify_enabled
        dc = self._cfg.discord_cfg
        webhook_url = dc.get("WebhookURL", "")

        if not notify_enabled:
            return

        if not re.search(PATTERN_WEBHOOK, webhook_url):
            notify_enabled = False
            self.notify_test = False
            print(
                f"{Terminal.WHITE}Info:{Terminal.END} "
                "Discord webhook missing or invalid — operating with terminal output only\n"
            )
            return

        self._discord_hook = DiscordWebhook(url=webhook_url)
        self._discord_up   = True

        if dc.get("Identity"):
            self._discord_hook.username   = "Elite Dangerous Monitor Daemon"
            self._discord_hook.avatar_url = AVATAR_URL

    def _restore_identity(self) -> None:
        dc = self._cfg.discord_cfg
        if dc.get("Identity") and self._discord_hook:
            self._discord_hook.username   = "Elite Dangerous Monitor Daemon"
            self._discord_hook.avatar_url = AVATAR_URL

    def _post(self, message: str) -> None:
        """Send a raw string to Discord (or echo in test mode)."""
        if not self._discord_up or not message:
            return
        if self.notify_test:
            print(f"{Terminal.WHITE}DISCORD:{Terminal.END} {message}")
            return
        try:
            self._discord_hook.content = message
            self._discord_hook.execute()
            self._restore_identity()
            dc = self._cfg.discord_cfg
            if (
                dc.get("ForumChannel")
                and self._discord_hook.thread_name
                and not self._discord_hook.thread_id
            ):
                self._discord_hook.thread_name = None
                self._discord_hook.thread_id   = self._discord_hook.id
        except Exception as e:
            print(f"{Terminal.WHITE}Discord:{Terminal.END} Webhook send error: {e}")

    def set_update_notice(self, version: str) -> None:
        """Schedule a deferred update notification for the next emit() call."""
        self._update_version         = version
        self._discord_update_pending = True

    def emit(
        self,
        msg_term,
        msg_discord=None,
        emoji=None,
        sigil=None,
        timestamp=None,
        loglevel: int = 2,
        event=None,
    ) -> None:
        state    = self._state
        cfg      = self._cfg
        dc       = cfg.discord_cfg
        settings = cfg.app_settings

        emoji_fmt   = f"{emoji} " if emoji else ""
        term_prefix = f"{sigil}  " if sigil else emoji_fmt
        loglevel    = int(loglevel)

        if state.in_preload and not self.notify_test:
            loglevel = 1 if loglevel > 0 else 0

        if timestamp:
            logtime = timestamp if settings.get("UseUTC") else timestamp.astimezone()
        else:
            logtime = (
                datetime.now(timezone.utc) if settings.get("UseUTC")
                else datetime.now()
            )

        logtime_str = datetime.strftime(logtime, "%H:%M:%S")
        state.logged += 1

        # ── Terminal ──────────────────────────────────────────────────────
        if loglevel > 0 and not self.notify_test and not self.gui_mode:
            print(f"[{logtime_str}] {term_prefix}{msg_term}")

        # ── GUI event log ─────────────────────────────────────────────────
        if self.gui_mode and loglevel > 0 and self._gui_queue:
            ansi_esc = re.compile(r"\x1b\[[0-9;]*m")
            clean    = ansi_esc.sub("", msg_term)
            self._gui_queue.put(("log", f"[{logtime_str}] {emoji_fmt}{clean}"))

        # ── Deferred Discord update notice ────────────────────────────────
        if self._discord_update_pending and self._discord_up and not self.notify_test:
            self._discord_update_pending = False
            from core.state import GITHUB_REPO
            repo_url = f"https://github.com/{GITHUB_REPO}"
            # _update_version is either "1.23" (release) or "+5 commits" (commits)
            if self._update_version and self._update_version.startswith("+"):
                content = (
                    f":arrow_up: **{self._update_version} available on main**"
                    f"  —  {repo_url}/commits/main"
                )
            else:
                content = (
                    f":arrow_up: **Update available: v{self._update_version}**"
                    f"  —  {repo_url}/releases"
                )
            try:
                upd_hook = DiscordWebhook(
                    url=dc.get("WebhookURL", ""),
                    content=content,
                    username="Elite Dangerous Monitor Daemon" if dc.get("Identity") else None,
                    avatar_url=AVATAR_URL if dc.get("Identity") else None,
                )
                upd_hook.execute()
            except Exception:
                pass

        # ── Discord ───────────────────────────────────────────────────────
        if self._discord_up and loglevel > 1:
            if event is not None and state.last_dup_key == event:
                state.dup_count += 1
            else:
                state.dup_count       = 1
                state.dup_suppressed  = False

            state.last_dup_key = event

            discord_message = msg_discord if msg_discord else f"**{msg_term}**"
            ping = (
                f" <@{dc.get('UserID', 0)}>"
                if loglevel > 2 and state.dup_count == 1
                else ""
            )
            ts_fmt    = f" {{{logtime_str}}}" if dc.get("Timestamp") else ""
            name_pfx  = (
                "" if not dc.get("PrependCmdrName")
                else f"[{state.pilot_name}] "
            )

            if state.dup_count <= MAX_DUPLICATES:
                self._post(f"{name_pfx}{emoji_fmt}{discord_message}{ts_fmt}{ping}")
            elif not state.dup_suppressed:
                self._post(f"{name_pfx}⏸️ **Suppressing further duplicate messages**{ts_fmt}")
                state.dup_suppressed = True

    def post_embed(self, embed) -> None:
        """Send a DiscordEmbed directly (used for startup embed)."""
        if not self._discord_up or not self._discord_hook:
            return
        try:
            self._discord_hook.add_embed(embed)
            self._discord_hook.execute()
            self._discord_hook.remove_embeds()
            self._restore_identity()
            dc = self._cfg.discord_cfg
            if (
                dc.get("ForumChannel")
                and self._discord_hook.thread_name
                and not self._discord_hook.thread_id
            ):
                self._discord_hook.thread_name = None
                self._discord_hook.thread_id   = self._discord_hook.id
        except Exception as e:
            print(f"{Terminal.WHITE}Discord:{Terminal.END} Startup embed error: {e}")


# ── Session summary ───────────────────────────────────────────────────────────

def emit_summary(emitter: "Emitter", state, providers: list, session_plugin) -> None:
    """Print a 15-minute session summary matching the GUI Summary tab exactly.

    providers      — core.session_providers list (ActivityProviderMixin instances)
    session_plugin — the session_stats plugin (for session_duration_seconds())
    """
    active = [p for p in providers if p.has_activity()]
    dur_s  = session_plugin.session_duration_seconds() if session_plugin else 0.0

    if not active and dur_s < 60:
        return   # nothing worth reporting

    logtime      = state.event_time
    duration_str = fmt_duration(dur_s)

    lines = [f"Session Summary — {duration_str}"]

    for p in sorted(active, key=lambda p: getattr(p, "ACTIVITY_TAB_TITLE", "")):
        rows = p.get_summary_rows()
        if not rows:
            continue
        title = getattr(p, "ACTIVITY_TAB_TITLE", "Activity")
        lines.append(f"  {title}")
        for r in rows:
            label = r.get("label", "")
            value = r.get("value", "")
            rate  = r.get("rate")
            if not value and not rate:
                continue  # section sub-header rows — skip in text form
            if rate:
                lines.append(f"    {label}: {value}  |  {rate}")
            else:
                lines.append(f"    {label}: {value}")

    if len(lines) == 1:
        return   # only the header line — nothing to send

    summary_text = "\n".join(lines)

    emitter.emit(
        msg_term=summary_text,
        msg_discord=f"```{summary_text}```",
        emoji="📊",
        sigil="~  SUMM",
        timestamp=logtime,
        loglevel=2,
    )

