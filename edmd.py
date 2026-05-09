#!/usr/bin/env python3
"""
edmd.py — Elite Dangerous Monitor Daemon — entry point

All business logic lives in the packages below:
  core/     — state, config, emit, journal loop, plugin loader, shared API
  components/ — all application components
  plugins/  — user plugin directory
"""

import argparse
import json
import os
import platform as _pl
import queue
import subprocess as _sp
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

# ── Ensure repo root is on sys.path ───────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from core.config import (
    ConfigManager,
    load_config_file,
    migrate_config_if_needed,
    resolve_config_path,
)
from core.emit import Terminal
from core.state import AUTHOR, DEBUG_MODE, GITHUB_REPO, PROGRAM, VERSION

# ── Argument parsing ──────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(
    prog=PROGRAM,
    description="Continuous monitoring of Elite Dangerous AFK sessions.",
)
parser.add_argument("-p", "--config_profile", help="Load a specific config profile")
parser.add_argument(
    "-g",
    "--gui",
    action="store_true",
    default=None,
    help="Launch the GUI instead of the terminal, will use TUI",
)
parser.add_argument(
    "-t",
    "--test",
    action="store_true",
    default=None,
    help="Re-route Discord output to terminal instead of webhook",
)
parser.add_argument(
    "-d",
    "--trace",
    action="store_true",
    default=None,
    help="Print verbose debug/trace output",
)
parser.add_argument(
    "--mode",
    choices=["terminal", "textual", "electron"],
    default=None,
    metavar="MODE",
    help="UI mode: terminal (default) | textual | electron",
)
parser.add_argument(
    "--log-file",
    metavar="PATH",
    help="Tee all terminal output to PATH (avoids pipe buffer deadlock)",
)
parser.add_argument(
    "--upgrade",
    action="store_true",
    default=False,
    help="Pull latest release and restart",
)
parser.add_argument(
    "--upgrade-nightly",
    action="store_true",
    default=False,
    help="Pull latest commit (nightly/dev) and restart",
)

args = parser.parse_args()


# ── Electron startup-error helper ────────────────────────────────────────────
# When running as an Electron subprocess, fatal startup errors are written to
# EDMD_DATA_DIR/electron-error.json so the renderer can show a friendly message
# instead of silently hanging until the JS port-file timeout fires.


def _electron_fatal(
    error_type: str,
    title: str,
    message: str,
    action: str = "",
    config_path: "str | None" = None,
) -> None:
    """Write electron-error.json and exit with code 1.

    Only does anything when EDMD is running as an Electron subprocess
    (detected via the EDMD_ELECTRON_LOG env var set by main.js).
    """
    import json as _json

    _electron_log = os.environ.get("EDMD_ELECTRON_LOG", "")
    if not _electron_log:
        # Not running under Electron — just print and let caller sys.exit
        return
    try:
        from core.state import EDMD_DATA_DIR as _data
    except Exception:
        return
    _err = {
        "type": error_type,
        "title": title,
        "message": message,
        "action": action,
        "config_path": str(config_path) if config_path else "",
    }
    try:
        (_data / "electron-error.json").write_text(
            _json.dumps(_err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ── In-place upgrade (self-contained — runs before full package import) ────────

# ── Git Based upgrades
# Will likely need to run through this a couple of times and make sure that it is
# pulling the correct data from the new repo, but until then, I'm half tempted to
# comment it out until I can get a different system in place.
"""
def _do_upgrade(nightly: bool = False) -> None:
    repo_dir = _HERE
    mode_label = "Nightly (dev)" if nightly else "Release"
    print(f"{Terminal.CYAN}{'=' * 52}\n  EDMD Upgrade — {mode_label}\n{'=' * 52}{Terminal.END}\n")

    import shutil
    if not shutil.which("git"):
        print(f"{Terminal.WARN}ERROR:{Terminal.END} git not found on PATH.")
        sys.exit(1)

    r = _sp.run(["git", "-C", str(repo_dir), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True)
    if r.returncode != 0:
        print(f"{Terminal.WARN}ERROR:{Terminal.END} {repo_dir} is not a git repository.")
        sys.exit(1)

    dirty = _sp.run(["git", "-C", str(repo_dir), "status", "--porcelain"],
                    capture_output=True, text=True)
    def _is_user_file(line: str) -> bool:
#        Return True if this git status line refers to a user-owned path
#        that should not block or warn on upgrade.
        path = line.strip().lstrip("?! MADRCU").strip()
        return (
            path.endswith("config.toml")
            or path.endswith("config.toml.bak")
            or path.startswith("plugins/")
            or path.startswith("plugins\\")
        )
    modified = [l for l in dirty.stdout.splitlines() if not _is_user_file(l)]

    label = "latest commit" if nightly else "latest release"
    print(f"  Current version : {VERSION}\n  Pulling         : {label} from origin/main")
    # Discard any local modifications to tracked files before pulling.
    # User data lives outside the repo (config.toml in ~/.local/share/EDMD/).
    _sp.run(["git", "-C", str(repo_dir), "checkout", "."],
            capture_output=True)
    pull_cmd = ["git", "-C", str(repo_dir), "pull"]
    if not nightly:
        pull_cmd.append("--ff-only")
    pull = _sp.run(pull_cmd, capture_output=True, text=True)
    if pull.returncode != 0:
        print(f"\n{Terminal.WARN}ERROR:{Terminal.END} git pull failed:")
        print(pull.stderr.strip() or pull.stdout.strip()); sys.exit(1)
    if "Already up to date" in pull.stdout:
        print(f"\n  Already up to date (v{VERSION}). Nothing to do.\n")
        sys.exit(0)
    print(pull.stdout.strip()); print()


    install_sh = repo_dir / "install.sh"
    if install_sh.exists():
        print("  Running install.sh...\n")
        inst = _sp.run(["bash", str(install_sh)], cwd=str(repo_dir))
        if inst.returncode != 0:
            print(f"\n{Terminal.WARN}Warning:{Terminal.END} install.sh exited with errors.")

    new_argv = [a for a in sys.argv if a not in ("--upgrade", "--upgrade-nightly")]
    print(f"\n{Terminal.GOOD}  Upgrade complete. Relaunching EDMD...{Terminal.END}\n")
    os.execv(sys.executable, [sys.executable] + new_argv)


if args.upgrade or getattr(args, "upgrade_nightly", False):
    _do_upgrade(nightly=getattr(args, "upgrade_nightly", False))
    sys.exit(0)  # unreachable — execv replaces process
"""
# This entire update sequence will need to be redone because of a upcoming semantic versioning change

# ── Header ────────────────────────────────────────────────────────────────────

title = f"{PROGRAM} v{VERSION} by {AUTHOR}"
print(f"{Terminal.CYAN}{'=' * len(title)}\n{title}\n{'=' * len(title)}{Terminal.END}\n")


# ── Background update check ───────────────────────────────────────────────────
# Checks two things in order of severity:
#   1. New tagged release on GitHub   → "release" notice
#   2. New commits on origin/main     → "commits" notice (only if git is present
#      and _HERE is a git working tree)
#
# _update_notice  = ("release", version_str)   — a tagged release is available
# _update_notice  = ("commits", N_str)          — N new commits ahead of local
# _update_notice  = None                        — nothing new
#
# In both cases File → Upgrade runs the same git-pull path.

"""
_update_notice: tuple[str, str] | None = None


def _check_for_update() -> None:
    global _update_notice
    import re as _re

    # Check for a newer tagged release via GitHub API.
    # Compares VERSION against the latest release tag using a (date, suffix) key
    # so 20260325a < 20260325b < 20260326 all sort correctly.
    # Commits that land on main after a release do NOT trigger a notice —
    # users who want nightly builds can run --upgrade themselves.

    # Will need to refactor this if we plan on moving to a different method of versioning and updates.
    # We can leave this for now though.

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        with urlopen(url, timeout=4) as resp:
            if resp.status == 200:
                tag = json.loads(resp.read()).get("tag_name", "").lstrip("v").strip()
                if tag and tag != VERSION:

                    def _vkey(v):
                        m = _re.match(r"^(\d+)([a-z]*)$", v)
                        return (int(m.group(1)), m.group(2)) if m else (0, "")

                    if _vkey(tag) > _vkey(VERSION):
                        _update_notice = ("release", tag)
    except Exception:
        pass


_update_thread = threading.Thread(target=_check_for_update, daemon=True)
_update_thread.start()
"""
# More Update code commenting...

# ── Config ────────────────────────────────────────────────────────────────────

config_path = resolve_config_path(Path(__file__))
if config_path is None:
    # No config found — generate a default one in the user data directory
    # so EDMD can start immediately.  The user can edit it via Preferences.
    from core.config import (
        CFG_DEFAULTS_DISCORD,
        CFG_DEFAULTS_EDASTRO,
        CFG_DEFAULTS_EDDN,
        CFG_DEFAULTS_EDSM,
        CFG_DEFAULTS_EXTRA,
        CFG_DEFAULTS_INARA,
        CFG_DEFAULTS_NOTIFY,
        CFG_DEFAULTS_SETTINGS,
        CFG_DEFAULTS_UI,
        config_to_toml,
    )
    from core.state import EDMD_DATA_DIR

    config_path = EDMD_DATA_DIR / "config.toml"
    _default_cfg = {
        "Settings": {**CFG_DEFAULTS_SETTINGS, **CFG_DEFAULTS_EXTRA},
        "Discord": CFG_DEFAULTS_DISCORD,
        "UI": CFG_DEFAULTS_UI,
        "LogLevels": CFG_DEFAULTS_NOTIFY,
        "EDDN": CFG_DEFAULTS_EDDN,
        "EDSM": CFG_DEFAULTS_EDSM,
        "EDAstro": CFG_DEFAULTS_EDASTRO,
        "Inara": CFG_DEFAULTS_INARA,
    }
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_to_toml(_default_cfg), encoding="utf-8")
        print(f"[EDMD] No config found — wrote default config to: {config_path}")
    except OSError as _e:
        print(
            f"{Terminal.WARN}WARNING:{Terminal.END} Could not write default config: {_e}"
        )
        # Fall through — ConfigManager will use built-in defaults

migrate_config_if_needed(
    config_path
)  # silently rewrite old [GUI]/sub-table format before loading
config_dict = load_config_file(config_path)
notify_test = bool(args.test) if args.test is not None else False
trace_mode = bool(args.trace) if args.trace is not None else DEBUG_MODE


# ── Log file (--log-file) ─────────────────────────────────────────────────────
# Opens a log file and tees ALL stdout output to it alongside the terminal.
# This is intentionally separate from shell redirection (> file) to avoid
# the pipe-buffer deadlock that occurs when running with --gui and --trace:
# shell pipes are bounded buffers; a blocked print() in the monitor thread
# stalls the journal loop, starving the GTK main loop of events.
# Opening the file directly bypasses the pipe entirely.

_log_fh = None

if args.log_file:
    import io as _io

    _log_path = Path(args.log_file).expanduser().resolve()
    try:
        _log_fh = open(_log_path, "w", encoding="utf-8", buffering=1)

        class _TeeWriter(_io.TextIOBase):
            """Write to both the original stdout and a log file simultaneously."""

            def __init__(self, primary, secondary):
                self._primary = primary
                self._secondary = secondary

            def write(self, text):
                self._primary.write(text)
                self._primary.flush()
                try:
                    self._secondary.write(text)
                    self._secondary.flush()
                except Exception:
                    pass
                return len(text)

            def flush(self):
                self._primary.flush()
                try:
                    self._secondary.flush()
                except Exception:
                    pass

            @property
            def encoding(self):
                return getattr(self._primary, "encoding", "utf-8")

        sys.stdout = _TeeWriter(sys.stdout, _log_fh)
        print(f"[EDMD] Logging to: {_log_path}")
    except OSError as _e:
        print(f"[EDMD] Warning: could not open log file {_log_path!r}: {_e}")
        _log_fh = None

# Preliminary manager — profile may be updated after commander name is known
mgr = ConfigManager(config_dict, config_path, config_profile=args.config_profile)


# ── State and session objects ─────────────────────────────────────────────────

from core.state import MonitorState, SessionData, load_session_state

state = MonitorState()
active_session = SessionData()
lifetime = SessionData()
gui_queue: queue.Queue = queue.Queue()


# ── Find journal ──────────────────────────────────────────────────────────────

from core.journal import find_latest_journal

journal_dir_str = mgr.app_settings.get("JournalFolder", "")
journal_dir = Path(journal_dir_str).expanduser() if journal_dir_str else None

if not journal_dir or not journal_dir.is_dir():
    # Auto-detect the standard Windows and Linux journal locations as a fallback.
    # This lets Electron users on Windows launch without needing config.toml.
    import platform as _platform

    _candidates = []
    if _platform.system() == "Windows":
        import os as _os

        _candidates = [
            Path(_os.environ.get("USERPROFILE", Path.home()))
            / "Saved Games"
            / "Frontier Developments"
            / "Elite Dangerous",
        ]
    # Might drop Mac support in the future.
    # Its a pain to work with at IRL work, don't want to do that here
    # Sorry Mac Users... But I don't think FDev supports you either
    elif _platform.system() == "Darwin":
        _candidates = [
            Path.home()
            / "Library"
            / "Application Support"
            / "Frontier Developments"
            / "Elite Dangerous",
        ]
    else:  # Linux — Steam common locations
        _candidates = [
            Path.home()
            / ".steam"
            / "steam"
            / "steamapps"
            / "compatdata"
            / "359320"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "Saved Games"
            / "Frontier Developments"
            / "Elite Dangerous",
            Path.home()
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "compatdata"
            / "359320"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "Saved Games"
            / "Frontier Developments"
            / "Elite Dangerous",
        ]
    for _c in _candidates:
        if _c.is_dir():
            print(f"[EDMD] JournalFolder not set — auto-detected: {_c}")
            journal_dir = _c
            journal_dir_str = str(_c)
            break
# Might change the logic here to give a OS specific message.
if not journal_dir or not journal_dir.is_dir():
    _msg = (
        f"JournalFolder is not set or the directory does not exist.\n\n"
        f"Configured path: {journal_dir_str!r}\n\n"
        f"Set JournalFolder in your config.toml to the Elite Dangerous journal directory.\n"
        f"On Windows the default location is:\n"
        f"  %USERPROFILE%\\Saved Games\\Frontier Developments\\Elite Dangerous"
    )
    print(f"{Terminal.WARN}ERROR:{Terminal.END} {_msg}")
    _electron_fatal(
        "no_journal",
        "Journal directory not found",
        _msg,
        action="Open config.toml and set JournalFolder, then restart EDMD.",
        config_path=config_path,
    )
    sys.exit(1)

journal_file = find_latest_journal(journal_dir)
if not journal_file:
    _msg = (
        f"No Elite Dangerous journal files found in:\n  {journal_dir}\n\n"
        f"Launch Elite Dangerous at least once to generate journal files, "
        f"or check that JournalFolder points to the correct directory."
    )
    print(f"{Terminal.WARN}ERROR:{Terminal.END} {_msg}")
    _electron_fatal(
        "no_journal_files",
        "No journal files found",
        _msg,
        action="Launch Elite Dangerous, then restart EDMD.",
        config_path=config_path,
    )
    sys.exit(1)


# ── Commander name — for profile auto-detection ───────────────────────────────

try:
    for _raw in journal_file.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            _j = json.loads(_raw.strip())
            if _j.get("event") in ("Commander", "LoadGame") and _j.get("Name"):
                state.pilot_name = _j["Name"]
                break
        except ValueError:
            pass
except OSError:
    pass

# ── Commander FID — for per-commander data directory ─────────────────────────
# Scan backwards through journals to find FID.  The current journal may only
# contain a Fileheader if the game just created it; prior journals are reliable.


def _scan_fid_from_journals(jdir: Path) -> str:
    """Return the Frontier account FID from the most recent journal that has one."""
    for _jp in sorted(jdir.glob("Journal*.log"), reverse=True):
        try:
            for _line in reversed(
                _jp.read_text(encoding="utf-8", errors="replace").splitlines()
            ):
                try:
                    _ev = json.loads(_line.strip())
                    if _ev.get("event") in ("Commander", "LoadGame") and _ev.get("FID"):
                        return _ev["FID"]
                except ValueError:
                    pass
        except OSError:
            pass
    return ""


from core.state import get_last_fid, set_active_fid

_fid = _scan_fid_from_journals(journal_dir) or get_last_fid()
if _fid:
    set_active_fid(_fid)
    state.pilot_fid = _fid
    print(f"{Terminal.YELL}Commander FID:{Terminal.END} {_fid}")
else:
    print(f"{Terminal.YELL}Commander FID:{Terminal.END} (not yet determined)")

print(f"{Terminal.YELL}Commander name:{Terminal.END} {state.pilot_name or '(unknown)'}")

_config_profile = args.config_profile
_config_info = ""
if not _config_profile and state.pilot_name and state.pilot_name in config_dict:
    _config_profile = state.pilot_name
    _config_info = " (auto)"
    mgr = ConfigManager(config_dict, config_path, config_profile=_config_profile)

print(
    f"{Terminal.YELL}Config profile:{Terminal.END} "
    f"{_config_profile or 'Default'}{_config_info}"
)


# ── UI mode ───────────────────────────────────────────────────────────────────
# Priority: --mode CLI flag > config [UI] Mode value > default

_cfg_mode = mgr.ui_cfg.get("Mode", "terminal").lower().strip()

if args.mode:
    ui_mode = args.mode
elif args.gui:
    ui_mode = "textual"
elif _cfg_mode in ("terminal", "textual", "electron"):
    ui_mode = _cfg_mode
else:
    ui_mode = "terminal"

gui_mode = ui_mode == "textual"
print(f"{Terminal.YELL}UI mode:{Terminal.END} {ui_mode}")


# ── Emitter ───────────────────────────────────────────────────────────────────
# What do you do I wonder...
from core.emit import Emitter, emit_summary

emitter = Emitter(
    mgr,
    state,
    gui_queue=gui_queue,
    notify_test=notify_test,
    gui_mode=gui_mode,
)


# ── CoreAPI + plugins ─────────────────────────────────────────────────────────

from core.core_api import CoreAPI
from core.data import DataProvider
from core.journal import build_dispatch_map
from core.plugin_loader import PluginLoader, PluginStorage
from core.state import EDMD_DATA_DIR, cmdr_data_dir

# DataProvider — unified source of truth, instantiated before CoreAPI
_dp_storage = PluginStorage(cmdr_data_dir() / "core")
data_provider = DataProvider(
    state=state,
    storage=_dp_storage,
    gui_queue_fn=lambda: gui_queue,
    print_fn=lambda m: print(m) if trace_mode else None,
)

core = CoreAPI(
    state=state,
    active_session=active_session,
    lifetime=lifetime,
    cfg_mgr=mgr,
    emitter=emitter,
    gui_queue=gui_queue,
    journal_dir=journal_dir,
    data_provider=data_provider,
    launch_argv=sys.argv,
)
data_provider._plugin_call = core.plugin_call

loader = PluginLoader(_HERE)
loader.load_all(core)
plugin_dispatch = build_dispatch_map(list(core._plugins.values()))
data_provider.start()  # start CAPI poll thread after plugins loaded


# ── Bootstrap from journal history ────────────────────────────────────────────

print("\nStarting... (Press Ctrl+C to stop)\n")

from core.journal import (
    bootstrap_burn_rate,
    bootstrap_crew,
    bootstrap_fighter_bay,
    bootstrap_missions,
    bootstrap_slf,
)

bootstrap_fighter_bay(state, journal_dir)
bootstrap_slf(state, journal_dir, trace_mode=trace_mode)
bootstrap_crew(state, journal_dir, trace_mode=trace_mode)
bootstrap_missions(state, journal_dir, mgr, trace_mode=trace_mode)
bootstrap_burn_rate(state, journal_dir, active_session, trace_mode=trace_mode)

# ── Update notice ─────────────────────────────────────────────────────────────
# Something is funky here... _update_notice is a tuple (kind, value) but _kind is always "release" now. Huh?
# Also... IDE thinks this code is inaccessible... HUH?!
# So... according to basedpyright...
# reportUnreachable [boolean or string, optional]:
# Generate or suppress diagnostics for code that is determined to be structurally unreachable or unreachable by type analysis.
"""
_update_thread.join(timeout=2)
if _update_notice:
    _kind, _value = _update_notice  # _kind is always "release" now.
    _repo_url = f"https://github.com/{GITHUB_REPO}"
    _term_msg = (
        f"{Terminal.YELL}\u26a0 Update available: v{_value}{Terminal.END}"
        f"  {Terminal.WHITE}{_repo_url}/releases{Terminal.END}\n"
        f"  Run {Terminal.CYAN}edmd.py --upgrade{Terminal.END} to update and restart automatically.\n"
    )
    if not gui_mode:
        print(_term_msg)
    emitter.set_update_notice(_value)
"""
# TODO: Fix this update code and figure out why its unreachable...
# Also TODO: Actually put in a proper update check and notification system.

# ── Session restore + startup banner ─────────────────────────────────────────

load_session_state(journal_file, active_session)
state.sessionstart(active_session)
emit_summary(
    emitter,
    state,
    core.session_providers,
    core._plugins.get("session_stats"),
)


# ── Monitor + launch ──────────────────────────────────────────────────────────

from core.journal import _poll_status_json
from core.journal import run_monitor as _run_monitor
from core.state import (
    save_session_state,  # Session state persistence? See state.py line 363
)

_edmd_start_mono = time.monotonic()


def run_monitor() -> None:
    _run_monitor(
        journal_file,
        state,
        active_session,
        lifetime,
        emitter,
        mgr,
        gui_queue,
        journal_dir,
        _edmd_start_mono,
        trace_mode=trace_mode,
        plugin_dispatch=plugin_dispatch,
        data_provider=data_provider,
        core=core,
    )


# Wonder why we are complaining about journal_file and journal_dir...

if __name__ == "__main__":
    if ui_mode == "textual":
        try:
            from tui.app import run_tui
        except ImportError as _tui_err:
            import traceback as _tb

            print(
                f"{Terminal.WARN}ERROR:{Terminal.END} Textual TUI import failed: {_tui_err}\n"
                f"sys.path: {sys.path}\n"
                f"Traceback:\n{_tb.format_exc()}"
                f"\nIf textual is missing: pip install textual"
            )
            sys.exit(1)

        _tui_theme = mgr.ui_cfg.get("Theme", "default")

        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()

        status_thread = threading.Thread(
            target=_poll_status_json,
            args=(journal_dir, state, gui_queue),
            daemon=True,
        )
        status_thread.start()

        run_tui(core, PROGRAM, VERSION, theme=_tui_theme)

    elif ui_mode == "electron":
        from core.electron_bridge import ElectronBridge

        bridge = ElectronBridge(core, gui_queue)
        port = bridge.start()

        if port == 0:
            _msg = (
                "The websockets Python package is not installed.\n\n"
                "Install it with:\n"
                "  pip install 'websockets>=12.0'"
            )
            print(
                f"{Terminal.WARN}ERROR:{Terminal.END} Electron bridge failed to start.\n{_msg}"
            )
            _electron_fatal(
                "no_websockets",
                "Missing Python dependency: websockets",
                _msg,
                action="Open a terminal and run:  pip install 'websockets>=12.0'",
                config_path=config_path,
            )
            sys.exit(1)

        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()

        status_thread = threading.Thread(
            target=_poll_status_json,
            args=(journal_dir, state, gui_queue),
            daemon=True,
        )
        status_thread.start()

        print(f"[EDMD] Electron bridge ready on port {port}. Waiting for renderer...")
        try:
            # Block until monitor exits or user presses Ctrl+C.
            # The monitor runs indefinitely during normal operation.
            # If it exits (e.g. journal dir gone, uncaught exception), we
            # log and keep the bridge alive so the renderer sees the disconnect.
            while True:
                monitor_thread.join(timeout=2.0)
                if not monitor_thread.is_alive():
                    print(
                        "[EDMD] Monitor thread exited — bridge staying up for renderer"
                    )
                    # Keep the main thread alive so the bridge stays running
                    # and the renderer can display a connection-lost state.
                    # Wait indefinitely (cross-platform) so the bridge
                    # stays alive for the renderer.
                    import time as _time

                    while True:
                        _time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            bridge.stop()

    else:  # terminal
        run_monitor()

    if _log_fh is not None:
        try:
            _log_fh.close()
        except Exception:
            pass
