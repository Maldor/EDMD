"""
edmd_launcher.py — EDMD Windows launcher stub

This file is compiled into EDMD.exe by PyInstaller.  It contains NO EDMD
application logic — it exists solely to locate the MSYS2 Python interpreter
and the EDMD source directory, set up the GTK4 DLL environment, and exec
edmd.py with the user's arguments.

Because the launcher does not freeze EDMD's Python code, the git-based
upgrade path (edmd.py --upgrade) continues to work: git pull updates the
source files on disk, and this launcher always picks up the latest source.

Layout after installation (default to %LOCALAPPDATA%\\EDMD):
    %LOCALAPPDATA%\\EDMD\\
        EDMD.exe            ← this launcher
        src\\                ← git clone of drworman/EDMD
            edmd.py
            core\\
            builtins\\
            ...
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────────

APP_NAME    = "EDMD"
MSYS2_ROOTS = [
    Path(r"C:\msys64"),
    Path(r"C:\msys2"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "msys64",
    Path(os.environ.get("LOCALAPPDATA", "")) / "msys2",
    Path(os.environ.get("ProgramFiles",  "")) / "msys64",
    Path(os.environ.get("ProgramFiles",  "")) / "msys2",
]
UCRT_SUBDIR = Path("ucrt64")
PYTHON_REL  = UCRT_SUBDIR / "bin" / "python.exe"
DLL_REL     = UCRT_SUBDIR / "bin"


def _show_error(title: str, message: str) -> None:
    """Show a Windows message box, fall back to stderr if ctypes fails."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(f"[EDMD] ERROR: {title}\n{message}", file=sys.stderr)


def _find_msys2() -> Path | None:
    """Return the root of the first MSYS2 installation found, or None."""
    # Also check MSYS2_ROOT env var set by the installer
    env_root = os.environ.get("EDMD_MSYS2_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / PYTHON_REL).exists():
            return p

    for root in MSYS2_ROOTS:
        if root.exists() and (root / PYTHON_REL).exists():
            return root
    return None


def _find_edmd_src() -> Path | None:
    """Locate edmd.py relative to EDMD.exe, falling back to env var."""
    # If EDMD.exe lives in %LOCALAPPDATA%\EDMD\, src\ is a sibling
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) \
              else Path(__file__).parent
    candidates = [
        exe_dir / "src",
        exe_dir,
        Path(os.environ.get("EDMD_SRC_DIR", "")),
    ]
    for c in candidates:
        if c and (c / "edmd.py").exists():
            return c
    return None


def main() -> None:
    # ── 1. Find EDMD source ───────────────────────────────────────────────────
    src_dir = _find_edmd_src()
    if src_dir is None:
        _show_error(
            "EDMD — Source not found",
            "Could not locate edmd.py.\n\n"
            "Expected at:\n"
            f"  {Path(sys.executable).parent}\\src\\edmd.py\n\n"
            "Re-run the EDMD installer to restore the source files.\n"
            "Alternatively, set EDMD_SRC_DIR to the directory containing edmd.py."
        )
        sys.exit(1)

    # ── 2. Find MSYS2 ─────────────────────────────────────────────────────────
    msys2_root = _find_msys2()
    if msys2_root is None:
        _show_error(
            "EDMD — MSYS2 not found",
            "EDMD requires MSYS2 (UCRT64) with GTK4 to run the GUI.\n\n"
            "Expected at one of:\n"
            "  C:\\msys64\\ucrt64\\bin\\python.exe\n"
            "  C:\\msys2\\ucrt64\\bin\\python.exe\n\n"
            "Re-run the EDMD installer, or install MSYS2 from https://msys2.org\n"
            "and run:  pacman -S mingw-w64-ucrt-x86_64-gtk4 "
            "mingw-w64-ucrt-x86_64-python-gobject\n\n"
            "Set EDMD_MSYS2_ROOT to override the search path."
        )
        sys.exit(1)

    python_exe = msys2_root / PYTHON_REL
    dll_dir    = msys2_root / DLL_REL

    # ── 3. Prepend MSYS2 UCRT64/bin to PATH (loads GTK4 DLLs) ───────────────
    env = os.environ.copy()
    env["PATH"] = str(dll_dir) + os.pathsep + env.get("PATH", "")
    env["EDMD_MSYS2_ROOT"] = str(msys2_root)
    env["EDMD_SRC_DIR"]    = str(src_dir)

    # ── 4. Exec edmd.py with all user arguments ───────────────────────────────
    edmd_py = src_dir / "edmd.py"
    cmd = [str(python_exe), str(edmd_py)] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        _show_error(
            "EDMD — Launch failed",
            f"Could not execute:\n  {python_exe}\n\n"
            "Verify that MSYS2 is installed correctly and re-run the EDMD installer."
        )
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
