"""
gui/blocks/assets.py — re-export AssetsBlock from the assets builtin plugin.

The block widget is defined in builtins/assets/plugin.py alongside the plugin
logic (same pattern as all other builtins).  This shim makes it importable
from gui.blocks for the EdmdWindow registry.
"""

from builtins.assets.plugin import AssetsBlock

__all__ = ["AssetsBlock"]
