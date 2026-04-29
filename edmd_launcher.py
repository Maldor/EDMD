"""
edmd_launcher.py — EDMD Windows launcher stub

Compiled into EDMD.exe by PyInstaller. Contains no EDMD application logic.
Locates the bundled Python runtime and launches edmd.py inside mintty — the
PTY emulator that ships with Git for Windows (a hard install dependency).

mintty provides a proper xterm-compatible terminal. This avoids the Windows
Console (conhost.exe) raw-mode hang that occurs when Textual exits uncleanly.

If mintty cannot be found, EDMD falls back to launching in the current console
directly, which works but may exhibit the raw-mode issue on abnormal exit.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _show_error(title: str, message: str) -> None:
    """Show a Windows message box, falling back to stderr."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        print(f"[EDMD] ERROR: {title}\n{message}", file=sys.stderr)


def _exe_dir() -> Path:
    """Directory containing EDMD.exe (or edmd_launcher.py in dev mode)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _find_edmd_src() -> Path | None:
    """Locate edmd.py relative to EDMD.exe, falling back to env var."""
    exe_dir = _exe_dir()
    candidates = [
        exe_dir / "src",
        exe_dir,
        Path(os.environ.get("EDMD_SRC_DIR", "")),
    ]
    for c in candidates:
        if c and (c / "edmd.py").exists():
            return c
    return None


# ── Bundled runtime ───────────────────────────────────────────────────────────

def _find_bundled_runtime() -> Path | None:
    """Return the bundled runtime directory if python.exe is present there."""
    runtime_dir = _exe_dir() / "runtime"
    if (runtime_dir / "python.exe").exists():
        return runtime_dir
    return None


def _setup_bundled_env(runtime_dir: Path, env: dict) -> None:
    """Configure the process environment for the bundled CPython runtime."""
    rt      = str(runtime_dir)
    rt_lib  = str(runtime_dir / "Lib")
    rt_pkgs = str(runtime_dir / "Lib" / "site-packages")
    rt_dlls = str(runtime_dir / "DLLs")

    # PATH: runtime dir and DLLs for the Windows DLL loader.
    existing_path = env.get("PATH", "")
    env["PATH"] = f"{rt};{rt_dlls};{existing_path}"

    # PYTHONHOME: tells CPython where its own stdlib lives.
    env["PYTHONHOME"] = rt

    # PYTHONPATH: our site-packages. Respected when no ._pth file suppresses it.
    env["PYTHONPATH"] = f"{rt_pkgs};{rt_lib};{rt_dlls}"

    env["EDMD_RUNTIME_DIR"] = rt


# ── mintty launcher ───────────────────────────────────────────────────────────
# mintty ships with Git for Windows, which is a hard install requirement.
# It provides a proper xterm-compatible PTY. Unlike conhost.exe, mintty
# handles terminal teardown cleanly even when a process exits abnormally,
# preventing the raw-mode hang that Textual can cause on Windows.

def _find_mintty() -> str | None:
    """Locate mintty.exe from the Git for Windows installation."""
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\GitForWindows") as k:
                    install_path, _ = winreg.QueryValueEx(k, "InstallPath")
                    candidate = Path(install_path) / "usr" / "bin" / "mintty.exe"
                    if candidate.exists():
                        return str(candidate)
            except OSError:
                pass
    except ImportError:
        pass

    # Fallback: known default install locations
    pf64     = os.environ.get("ProgramFiles", r"C:\Program Files")
    localapp = os.environ.get("LOCALAPPDATA", "")
    for base in [pf64, localapp and str(Path(localapp) / "Programs")]:
        if not base:
            continue
        candidate = Path(base) / "Git" / "usr" / "bin" / "mintty.exe"
        if candidate.exists():
            return str(candidate)

    return None


def _launch_in_mintty(mintty: str, python_exe: Path, edmd_py: Path,
                      env: dict, extra_args: list[str]) -> None:
    """Spawn edmd.py inside a mintty window and exit the stub.

    mintty flags used:
      --title  window title bar text
      --window full  start maximised
      -e       command mintty will exec (keeps window open until it exits)
    """
    cmd = [
        mintty,
        "--title", "EDMD",
        "--window", "full",
        "-e",
        str(python_exe),
        str(edmd_py),
    ] + extra_args

    subprocess.Popen(cmd, env=env, creationflags=subprocess.DETACHED_PROCESS)
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Find EDMD source (git clone in src/)
    src_dir = _find_edmd_src()
    if src_dir is None:
        exe = _exe_dir()
        _show_error(
            "EDMD -- Source not found",
            "Could not locate edmd.py.\n\n"
            "Expected at:\n"
            f"  {exe / 'src' / 'edmd.py'}\n\n"
            "Re-run the EDMD installer to restore the source files.\n"
            "Alternatively set EDMD_SRC_DIR to the directory containing edmd.py."
        )
        sys.exit(1)

    # 2. Locate bundled Python runtime
    runtime_dir = _find_bundled_runtime()
    if runtime_dir is None:
        exe = _exe_dir()
        _show_error(
            "EDMD -- Python runtime not found",
            "EDMD requires a bundled Python runtime.\n\n"
            "Expected at:\n"
            f"  {exe / 'runtime' / 'python.exe'}\n\n"
            "Re-run the EDMD installer to restore the runtime."
        )
        sys.exit(1)

    env = os.environ.copy()
    env["EDMD_SRC_DIR"] = str(src_dir)
    _setup_bundled_env(runtime_dir, env)
    python_exe = runtime_dir / "python.exe"
    edmd_py    = src_dir / "edmd.py"

    # 3. If not already inside mintty, launch mintty and exit this stub.
    #    mintty sets TERM in its child processes; absence means we are not
    #    running inside a proper PTY yet.
    if sys.platform == "win32" and not os.environ.get("TERM"):
        mintty = _find_mintty()
        if mintty:
            _launch_in_mintty(mintty, python_exe, edmd_py, env, sys.argv[1:])
        # mintty not found — fall through and run directly in the current console

    # 4. Launch edmd.py directly (inside mintty, or fallback)
    cmd = [str(python_exe), str(edmd_py)] + sys.argv[1:]
    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        _show_error(
            "EDMD -- Launch failed",
            f"Could not execute Python:\n  {python_exe}\n\n"
            "Re-run the EDMD installer to restore the runtime."
        )
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
