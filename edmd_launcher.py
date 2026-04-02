"""
edmd_launcher.py -- EDMD Windows launcher stub

Compiled into EDMD.exe by PyInstaller. Contains no EDMD application logic.
Locates a Python interpreter, configures the GTK4 environment, and execs
edmd.py with the user's arguments.

Runtime priority order:
  1. Bundled runtime  (runtime/python.exe sibling to EDMD.exe) -- new installs.
     Ships with the installer; no MSYS2 required on the user machine.
  2. MSYS2 fallback   (ucrt64/bin/python.exe) -- developer machines and
     users of older installers who have MSYS2 installed locally.

The EDMD source lives in src/ as a real git clone, so the git-based upgrade
path (EDMD.exe --upgrade) is preserved regardless of which runtime is active.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path


# ---- Constants: MSYS2 fallback -----------------------------------------------

APP_NAME    = "EDMD"
UCRT_SUBDIR = Path("ucrt64")
PYTHON_REL  = UCRT_SUBDIR / "bin" / "python.exe"
DLL_REL     = UCRT_SUBDIR / "bin"

MSYS2_ROOTS = [
    Path(r"C:\msys64"),
    Path(r"C:\msys2"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "msys64",
    Path(os.environ.get("LOCALAPPDATA", "")) / "msys2",
    Path(os.environ.get("ProgramFiles",  "")) / "msys64",
    Path(os.environ.get("ProgramFiles",  "")) / "msys2",
]


# ---- Helpers -----------------------------------------------------------------

def _show_error(title: str, message: str) -> None:
    """Show a Windows message box, falling back to stderr."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
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


# ---- Priority 1: Bundled runtime ---------------------------------------------

def _find_bundled_runtime() -> Path | None:
    """
    Return the bundled runtime directory if python.exe is present there.

    The bundled runtime is assembled at build time by scripts/collect_runtime.ps1
    and installed to {app}/runtime/ by the Inno Setup installer.
    """
    runtime_dir = _exe_dir() / "runtime"
    if (runtime_dir / "python.exe").exists():
        return runtime_dir
    return None


def _setup_bundled_env(runtime_dir: Path, env: dict) -> None:
    """
    Configure the process environment for the bundled runtime.

    The runtime directory contains python.exe alongside all GTK4 DLLs.
    A python<ver>._pth file in the same directory tells Python where to
    find its stdlib relative to the executable (no hardcoded prefix needed).
    """
    rt = str(runtime_dir)

    # Prepend runtime dir to PATH so python.exe finds its sibling DLLs
    env["PATH"] = rt + os.pathsep + env.get("PATH", "")

    # GI typelib path (Gtk-4.0.typelib etc.)
    typelib = runtime_dir / "lib" / "girepository-1.0"
    if typelib.exists():
        env["GI_TYPELIB_PATH"] = str(typelib)

    # XDG_DATA_DIRS -- tells GTK4 where compiled schemas and icons live
    share = runtime_dir / "share"
    if share.exists():
        existing = env.get("XDG_DATA_DIRS", "")
        env["XDG_DATA_DIRS"] = str(share) + (os.pathsep + existing if existing else "")

    env["EDMD_RUNTIME_DIR"] = rt


# ---- Priority 2: MSYS2 fallback ----------------------------------------------

def _find_msys2() -> Path | None:
    """Return the MSYS2 root if it contains a UCRT64 Python installation."""
    env_root = os.environ.get("EDMD_MSYS2_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / PYTHON_REL).exists():
            return p
    for root in MSYS2_ROOTS:
        if root.exists() and (root / PYTHON_REL).exists():
            return root
    return None


def _setup_msys2_env(msys2_root: Path, env: dict) -> Path:
    """
    Configure the environment for MSYS2 UCRT64 Python.
    Returns the path to python.exe.
    """
    python_exe = msys2_root / PYTHON_REL
    dll_dir    = msys2_root / DLL_REL

    # Prepend UCRT64/bin so GTK4 DLLs are found
    env["PATH"] = str(dll_dir) + os.pathsep + env.get("PATH", "")

    # When not launched from an MSYS2 login shell, pip-installed packages
    # may not be on sys.path. Set PYTHONPATH explicitly as a safety net.
    lib_dir = msys2_root / UCRT_SUBDIR / "lib"
    for candidate in sorted(lib_dir.glob("python3.*"), reverse=True):
        sp = candidate / "site-packages"
        if sp.exists():
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(sp) + (os.pathsep + existing if existing else "")
            break

    env["EDMD_MSYS2_ROOT"] = str(msys2_root)
    return python_exe


# ---- Main --------------------------------------------------------------------

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

    env = os.environ.copy()
    env["EDMD_SRC_DIR"] = str(src_dir)

    # 2. Locate Python runtime
    python_exe: Path | None = None

    runtime_dir = _find_bundled_runtime()
    if runtime_dir is not None:
        _setup_bundled_env(runtime_dir, env)
        python_exe = runtime_dir / "python.exe"

    if python_exe is None:
        msys2_root = _find_msys2()
        if msys2_root is not None:
            python_exe = _setup_msys2_env(msys2_root, env)

    if python_exe is None:
        exe = _exe_dir()
        _show_error(
            "EDMD -- Python runtime not found",
            "EDMD requires a bundled runtime or MSYS2 (UCRT64) with GTK4.\n\n"
            "Bundled runtime expected at:\n"
            f"  {exe / 'runtime' / 'python.exe'}\n\n"
            "MSYS2 searched at:\n"
            "  C:\\msys64  |  C:\\msys2  |  %LOCALAPPDATA%\\msys64\n\n"
            "Re-run the EDMD installer to restore the runtime.\n"
            "Set EDMD_MSYS2_ROOT to override the MSYS2 search path."
        )
        sys.exit(1)

    # 3. Launch edmd.py
    edmd_py = src_dir / "edmd.py"
    cmd = [str(python_exe), str(edmd_py)] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        _show_error(
            "EDMD -- Launch failed",
            f"Could not execute Python:\n  {python_exe}\n\n"
            "Verify the runtime or MSYS2 installation and re-run the EDMD installer."
        )
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
