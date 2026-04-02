"""
core/install_context.py — Installation method detection.

Determines how EDMD was installed and exposes that information to the rest
of the application so that upgrade paths and help text can be presented
appropriately rather than offering workflows that don't apply.

Detection logic
───────────────
Flatpak      /.flatpak-info exists (created by the Flatpak runtime inside every
             sandbox) AND the FLATPAK_ID environment variable matches our App ID.
             Both checks are required — /.flatpak-info could theoretically exist
             in other container runtimes, and FLATPAK_ID alone could be spoofed.

Windows      sys.platform == "win32".  Within Windows installs, the sub-type
             (bundled runtime vs. MSYS2) is indicated by EDMD_RUNTIME_DIR being
             set in the environment (written by the launcher when it finds the
             bundled runtime directory).

Git / dev    Any other install: a plain git clone or pip-installed development
             setup on Linux or macOS.  The full upgrade path is available.

These categories are mutually exclusive.  The module exposes a single
InstallContext instance at the module level; consumers import it directly:

    from core.install_context import install_context
    if install_context.is_flatpak:
        ...
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass


FLATPAK_APP_ID = "io.github.drworman.EDMD"


@dataclass(frozen=True)
class InstallContext:
    """Immutable description of how EDMD was installed."""

    is_flatpak:         bool   # running inside a Flatpak sandbox
    is_windows:         bool   # running on Windows
    has_bundled_runtime: bool   # Windows installer with bundled runtime (not MSYS2)
    is_git:             bool   # plain git clone / dev install

    @property
    def upgrade_mode(self) -> str:
        """
        Short string describing the available upgrade mechanism.

        Returns one of:
          "flatpak"   — update via ``flatpak update``
          "git"       — update via ``git pull`` / ``--upgrade``
          "windows"   — update via git pull (launcher handles it)
        """
        if self.is_flatpak:
            return "flatpak"
        if self.is_windows:
            return "windows"
        return "git"


def _detect() -> InstallContext:
    is_flatpak = (
        Path("/.flatpak-info").exists()
        and os.environ.get("FLATPAK_ID", "") == FLATPAK_APP_ID
    )
    is_windows = sys.platform == "win32"
    has_bundled = bool(os.environ.get("EDMD_RUNTIME_DIR"))

    return InstallContext(
        is_flatpak          = is_flatpak,
        is_windows          = is_windows,
        has_bundled_runtime = is_windows and has_bundled,
        is_git              = not is_flatpak and not is_windows,
    )


# Module-level singleton — created once at import time.
install_context: InstallContext = _detect()
