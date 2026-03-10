# EDMD Plugin Development

EDMD supports user-written plugins. Drop a plugin into `plugins/<n>/plugin.py`
and it will be loaded automatically on startup alongside the built-in modules.

> **Stability note:** The plugin API and block system interfaces are stable as of v20260310.

The `plugins/` directory is gitignored — your work survives `--upgrade`.

---

## Plugin structure

```
plugins/
└── myplugin/
    └── plugin.py
```

---

## Minimal plugin (event handler only)

```python
from core.plugin_loader import BasePlugin

class MyPlugin(BasePlugin):
    PLUGIN_NAME       = "myplugin"
    PLUGIN_DISPLAY    = "My Plugin"
    PLUGIN_VERSION    = "1.0.0"
    SUBSCRIBED_EVENTS = ["Bounty", "FactionKillBond"]

    def on_load(self, core) -> None:
        self.core = core

    def on_event(self, event: dict, state) -> None:
        reward = event.get("TotalReward", 0)
        # event  — the parsed journal line (dict)
        # state  — live MonitorState
```

---

## Plugin class attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `PLUGIN_NAME` | Yes | Internal identifier. Must be unique. Lowercase, no spaces. |
| `PLUGIN_DISPLAY` | Yes | Human-readable name shown in the Installed Plugins dialog. |
| `PLUGIN_VERSION` | Yes | Freeform version string. |
| `PLUGIN_DESCRIPTION` | No | One-line description shown in the Installed Plugins dialog. |
| `PLUGIN_DEFAULT_ENABLED` | No | Set `False` to ship the plugin disabled. Users opt in via the dialog. Default: `True`. |
| `SUBSCRIBED_EVENTS` | No | List of Elite journal event names to receive. |
| `BLOCK_WIDGET_CLASS` | No | A `BlockWidget` subclass to register as a dashboard block. |

---

## Plugin lifecycle

```python
def on_load(self, core) -> None:
    """Called once when the plugin is loaded at startup."""

def on_unload(self) -> None:
    """Called on clean shutdown. Release any resources."""

def on_event(self, event: dict, state) -> None:
    """Called for every event in SUBSCRIBED_EVENTS."""
```

`on_load` fires after the journal monitor has started but before preload replay.
Use it to read saved state from `self.storage`, register your block, and grab a
reference to `core`.

---

## Persistent storage

Every plugin gets a sandboxed storage directory at
`EDMD_DATA_DIR/plugins/<plugin_name>/`. Access it via `self.storage`:

```python
def on_load(self, core) -> None:
    data = self.storage.read_json("data.json")       # returns {} if absent
    self._count = data.get("count", 0) + 1
    self.storage.write_json({"count": self._count}, "data.json")
```

| Method | Description |
|--------|-------------|
| `self.storage.read_json(filename)` | Read a JSON file. Returns `{}` if absent. |
| `self.storage.write_json(data, filename)` | Write a JSON file. |
| `self.storage.read_toml(filename)` | Read a TOML file. Returns `{}` if absent. |
| `self.storage.path` | `Path` to your plugin's data directory. |

Allowed filenames: `data.json`, `config.json`, `state.json`, `config.toml`, `state.toml`.

---

## Adding a dashboard block

Plugins can register a native dashboard block. The framework provides all chrome:
frame, section header, drag-to-move, resize handle, collapse toggle, and footer
gutter. Your plugin only fills the content area.

**Consistency is structurally guaranteed.** A plugin cannot alter the chrome because
it is owned entirely by `BlockWidget`. The dashboard will always look consistent
regardless of who wrote the plugin.

### Step 1 — Write a BlockWidget subclass

```python
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    _GTK = True
except Exception:
    _GTK = False

if _GTK:
    from gui.block_base import BlockWidget

if _GTK:
    class MyBlock(BlockWidget):
        BLOCK_TITLE = "My Plugin"   # section header text

        # Default grid position — used when the user has no saved layout entry.
        # Users can drag and resize freely; their layout is saved automatically.
        DEFAULT_COL    = 0
        DEFAULT_ROW    = 0
        DEFAULT_WIDTH  = 8    # grid columns (out of 24)
        DEFAULT_HEIGHT = 8    # row units

        def build(self, parent: "Gtk.Box") -> None:
            """Populate the content area. Called once at startup."""
            body = self._build_section(parent)   # returns the inner content box

            self._value_lbl = self.make_label("—", css_class="data-value")
            body.append(self.make_row("Kills today"))
            body.append(self._value_lbl)

        def refresh(self) -> None:
            """Called every second and on plugin_refresh queue messages."""
            count = getattr(self.state, "my_kill_count", 0)
            self._value_lbl.set_label(str(count))
```

### Step 2 — Register it on your plugin

```python
class MyPlugin(BasePlugin):
    PLUGIN_NAME        = "myplugin"
    PLUGIN_DISPLAY     = "My Plugin"
    PLUGIN_VERSION     = "1.0.0"
    SUBSCRIBED_EVENTS  = ["Bounty"]
    BLOCK_WIDGET_CLASS = MyBlock if _GTK else None   # this is all that's needed

    def on_load(self, core) -> None:
        self.core = core

    def on_event(self, event: dict, state) -> None:
        if event.get("event") == "Bounty":
            if self.core.gui_queue:
                self.core.gui_queue.put(("plugin_refresh", self.PLUGIN_NAME))
```

The GUI automatically places your block on the canvas, adds it to the
View → Blocks show/hide list, and calls `refresh()` every second.

---

## Block behaviours reference

Every block built on `BlockWidget` inherits the following behaviours
automatically — no extra code required in your plugin.

### Drag to move

The section header is a drag handle. Click and drag it to reposition the block
on the canvas. The block snaps to the nearest grid column and row on release.
The new position is saved to `layout.json` immediately.

During a drag, a lightweight ghost frame follows the cursor. The real block
does not move until the gesture ends, eliminating stutter.

### Resize

A resize handle (⤡) lives in the bottom-right corner of every block's footer
gutter. Drag it to resize. The block snaps to the nearest column and row unit
on release. The new size is saved automatically.

### Collapse / expand

**Double-click the section header** to collapse a block to just its title bar.
Double-click again to restore it. The block occupies only the height of its
header while collapsed, freeing screen space on crowded dashboards.

Collapse state is not persisted — blocks come back expanded on restart.

While collapsed, the block's grid position and size are preserved. On expand,
it returns to its full allocated size without needing a layout reset.

### Width-responsive layout

If your block needs to respond to its own pixel width (e.g. switching between
a compact and an expanded layout), override `on_resize`:

```python
WIDE_THRESHOLD = 380   # pixels

def on_resize(self, w: int, h: int) -> None:
    super().on_resize(w, h)   # REQUIRED — enforces collapsed height
    if w >= WIDE_THRESHOLD:
        self._show_wide_layout()
    else:
        self._show_narrow_layout()
```

`on_resize` is called after every `set_size_request` — on window resize, block
resize, and reflow. Always call `super().on_resize(w, h)` first so the base
class can enforce the collapsed height if the block is currently collapsed.

---

## BlockWidget API reference

Methods and attributes available inside your `BlockWidget` subclass:

| Method / Attribute | Returns | Description |
|--------------------|---------|-------------|
| `self._build_section(parent, title)` | `Gtk.Box` | Sets up section header and separator; returns inner content box. Must be called at the start of `build()`. |
| `self.make_label(text, css_class, xalign)` | `Gtk.Label` | Create a styled label. |
| `self.make_row(key_text, value_text)` | `Gtk.Box` | Create a key / value row. |
| `self.footer()` | `Gtk.Box` | Footer gutter box. Prepend status items here (before the spacer). |
| `self.state` | `MonitorState` | Live game state. |
| `self.session` | `SessionData` | Current session data. |
| `self.core` | `CoreAPI` | Full core API. |
| `self.fmt_credits(n)` | `str` | Format a credit value — e.g. `1.50M`. |
| `self.fmt_duration(s)` | `str` | Format seconds — e.g. `1h 30m`. |
| `self._name` | `str` | Your block's plugin name. Available after `build_widget` is called. |

### BlockWidget class attributes

| Attribute | Default | Description |
|-----------|---------|-------------|
| `BLOCK_TITLE` | `"Block"` | Section header text. |
| `BLOCK_CSS` | `"block"` | CSS class added to the outer section box. |
| `DEFAULT_COL` | — | Default grid column when no saved layout entry exists. |
| `DEFAULT_ROW` | — | Default grid row. |
| `DEFAULT_WIDTH` | — | Default width in grid columns (max 24). |
| `DEFAULT_HEIGHT` | — | Default height in row units. |

If `DEFAULT_COL` is not declared, the block falls back to `col=0, row=0` with
minimum size. Always declare all four defaults together.

---

## CoreAPI reference

Your plugin receives a `CoreAPI` instance via `on_load`:

| Attribute / Method | Description |
|--------------------|-------------|
| `core.state` | Live `MonitorState` |
| `core.active_session` | `SessionData` for the current session |
| `core.cfg` | `ConfigManager` — use `.pcfg(key)` for profile-aware lookup |
| `core.journal_dir` | `Path` to the active journal directory |
| `core.emit(msg_term, msg_discord, ...)` | Post to terminal, GUI log, and Discord |
| `core.gui_queue` | Thread-safe queue for GUI update messages |
| `core.plugin_call(name, method, *args)` | Call a method on another loaded plugin |
| `core.fmt_credits(n)` | Format a credit value — e.g. `1.50M` |
| `core.fmt_duration(s)` | Format seconds — e.g. `1h 30m` |

---

## GUI queue message types

| Message type | Payload | Effect |
|---|---|---|
| `plugin_refresh` | plugin name `str` | Calls `refresh()` on that plugin's block |
| `all_update` | `None` | Refreshes all blocks |
| `cmdr_update` | `None` | Refreshes Commander block |
| `stats_update` | `None` | Refreshes Session Stats block |
| `mission_update` | `None` | Refreshes Mission Stack block |
| `crew_update` / `slf_update` | `None` | Refreshes Crew / SLF block |
| `alerts_update` | `None` | Refreshes Alerts block |
| `update_notice` | version string | Shows update badge in the header bar |

---

## CSS classes

The following CSS classes are available on all block widgets.

| Class | Applied to | Description |
|-------|-----------|-------------|
| `dashboard-block` | frame | Outer block frame |
| `panel-section` | outer box | Section container |
| `section-header` | header label | Block title bar |
| `section-sep` | separator | Line below the title |
| `section-body` | inner box | Content area returned by `_build_section` |
| `block-footer` | footer box | Footer gutter row |
| `data-row` | row box | A key/value pair row |
| `data-key` | label | Dim key or secondary text |
| `data-value` | label | Primary value text |
| `block-dragging` | frame | Applied during a drag gesture |
| `block-resizing` | frame | Applied during a resize gesture |
| `block-drag-ghost` | ghost frame | Ghost overlay during drag/resize |

---

## The Welcome plugin

`plugins/welcome/plugin.py` is a working example plugin that demonstrates every
concept in this guide. It ships disabled (`PLUGIN_DEFAULT_ENABLED = False`) and
can be enabled in **File → Installed Plugins**.

It demonstrates: GTK guard pattern, `_build_section`, `make_label`, `refresh`,
`SUBSCRIBED_EVENTS`, `self.storage`, `DEFAULT_COL/ROW/WIDTH/HEIGHT`,
and `PLUGIN_DEFAULT_ENABLED`.

Read it alongside this document.

---

## Checklist for a new plugin

- [ ] `PLUGIN_NAME` is lowercase, unique, no spaces
- [ ] `PLUGIN_VERSION` is set
- [ ] All GTK imports are guarded with `try/except`
- [ ] `BLOCK_WIDGET_CLASS = MyBlock if _GTK else None`
- [ ] `DEFAULT_COL`, `DEFAULT_ROW`, `DEFAULT_WIDTH`, `DEFAULT_HEIGHT` are all declared
- [ ] `build()` calls `self._build_section(parent)` first
- [ ] `refresh()` is side-effect safe — it fires every second
- [ ] `on_resize()` calls `super().on_resize(w, h)` first if overridden
- [ ] Plugin is tested with GUI disabled (terminal-only mode)
