"""
gui — EDMD GTK4 dashboard package.

Public surface for edmd.py GUI entry point.
"""

from gui.helpers import (
    # PP helpers
    pp_merits_for_rank,
    pp_rank_progress,
    PP_RANK_NAMES,
    # Theme
    load_theme,
    apply_theme,
    avatar_path_for_theme,
    THEMES_DIR,
    # Widget factories
    make_label,
    make_section,
    make_row,
    # Health helpers
    hull_css,
    set_health_label,
    fmt_shield,
    fmt_crew_active,
)

__all__ = [
    "pp_merits_for_rank", "pp_rank_progress", "PP_RANK_NAMES",
    "load_theme", "apply_theme", "avatar_path_for_theme", "THEMES_DIR",
    "make_label", "make_section", "make_row",
    "hull_css", "set_health_label", "fmt_shield", "fmt_crew_active",
]

# ── Application (imported lazily to avoid GTK init at module level) ────────────
# from gui.app import EdmdWindow, EdmdApp   # import these directly when needed
