# EDMD Release Notes

---

## 20260328

**Elite Dangerous Monitor Daemon — EDMD**

Feature and polish release. Introduces JetBrains Mono as the bundled default
font with a monospace font picker and font size control in Preferences. Fixes
stale ship and carrier data in the Assets block. Corrects pipe-delimiter
alignment in the Session Stats Summary tab. Includes a community CSS template
contribution.

---

### Feature — Bundled Font: JetBrains Mono

EDMD now ships with JetBrains Mono as its default GUI font. The four TTF
weights (Regular, Bold, Italic, Bold Italic) are bundled in `fonts/` and
registered at startup via PangoCairo — no system font directories are written,
no font cache rebuild is required, and the font is scoped entirely to the EDMD
process.

On first GUI launch EDMD copies the TTF files into its own data directory
(`~/.local/share/EDMD/fonts/` on Linux/macOS, `%APPDATA%\EDMD\fonts\` on
Windows) and registers them with `PangoCairo.FontMap.add_font_file()`. If the
`fonts/` directory is empty EDMD falls back silently to the system monospace
font. This approach is fully cross-platform and leaves no cruft outside the
EDMD data directory.

---

### Feature — Font Preferences

Two new settings in **Settings → Appearance**:

**Font Family** — dropdown listing all installed monospace fonts detected via
`Pango.FontMap.list_families()`. JetBrains Mono is the default and always
appears first in the list. Any installed monospace font can be selected.

**Font Size** — spinner from 10–24 px. All element sizes in `base.css` are
expressed in `em` relative to this base, so the entire UI scales
proportionally. Default is 14 px.

Both settings are saved to `config.toml [GUI]` and take effect on next launch.

Config keys:

```toml
[GUI]
FontFamily = "JetBrains Mono"   # any installed monospace font
FontSize   = 14                  # 10–24 px
```

---

### Enhancement — CSS Theme Template  *(community contribution)*

The `themes/custom-template.css` file has been overhauled with improved
inline documentation covering all available CSS custom properties, their
semantic meaning, and guidance on constructing hover `rgba()` values from hex
accent colours.

A note has been added clarifying that font family and font size are controlled
via Preferences rather than CSS variables, since GTK4's CSS engine does not
support `var()` for `font-family`.

*Contributed by [Maldor](https://github.com/Maldor) via
[PR #2](https://github.com/drworman/EDMD/pull/2). Thank you!*

---

### Fix — Session Stats: Pipe Delimiter Alignment

The `|` separator in the Session Stats Summary tab was misaligned across
sections — Combat's pipe column, Exploration's pipe column, and Missions's
pipe column were each sized independently because each section had its own
`Gtk.Grid`. GTK sizes grid columns per-instance, so the wider `"8 jumps"`
value in Exploration's value column pushed its pipe further right than the
narrower combat values.

The Summary tab now uses a single shared `Gtk.Grid` for all sections,
including Duration and all provider sections. GTK sizes the value and rate
columns globally across every row, so all `|` delimiters land at the same
horizontal position regardless of which section they belong to. Activity tabs
each keep their own grid — per-tab alignment is correct there.

---

### Fix — Assets Block: Sold Ships Not Removed

When a ship was sold (`ShipyardSell`) or transferred to another player, it
remained visible in the Assets Ships tab until the next shipyard visit fired
a `StoredShips` event. EDMD now subscribes to `ShipyardSell` directly. On
receipt, the sold `ShipID` is removed from the loadout cache and from the
in-memory stored fleet immediately, so the display updates without waiting
for a subsequent event.

For CAPI-unavailable installs, the `_ship_loadout_cache` is now also pruned
against the most recent `StoredShips` event on every startup — preventing
sold ships from accumulating in the persistent cache across restarts when CAPI
is not authenticated.

---

### Fix — Assets Block: Decommissioned Carrier Not Removed

`CarrierDecommission` was not subscribed. If a player decommissioned their
fleet carrier, `assets_carrier` would persist indefinitely — no `CarrierStats`
ever fires again for a decommissioned carrier. EDMD now subscribes to
`CarrierDecommission` and clears `state.assets_carrier` immediately, queuing
a GUI refresh.

---

### Files Changed

| File | Change |
|------|--------|
| `core/state.py` | VERSION → 20260328 |
| `core/components/assets/plugin.py` | `ShipyardSell` and `CarrierDecommission` subscribed and handled; `_ship_loadout_cache` pruned against `StoredShips` when CAPI unavailable |
| `core/config.py` | `FontFamily` and `FontSize` added to `CFG_DEFAULTS_GUI` |
| `gui/helpers.py` | `bootstrap_fonts()`, `list_monospace_fonts()` added; `load_theme()` and `apply_theme()` accept `font_size` and `font_family` |
| `gui/app.py` | Reads `FontFamily` and `FontSize` from config; calls `bootstrap_fonts()` before `apply_theme()` |
| `gui/preferences.py` | Font Family dropdown and Font Size spinner added to Appearance tab |
| `gui/blocks/session_stats.py` | Summary tab uses a single shared `Gtk.Grid` across all sections |
| `themes/base.css` | `--font-size` CSS variable; `font-family: "JetBrains Mono", monospace` on `.edmd-window` |
| `themes/custom-template.css` | Overhauled documentation; font guidance added *(Maldor, PR #2)* |
| `example.config.toml` | `FontFamily` and `FontSize` documented in `[GUI]` section |
| `INSTALL.md` | Font section updated to reflect self-managing per-process approach |
| `install.sh` | Font section removed (handled at runtime) |
| `install.bat` | Font section removed (handled at runtime) |
| `fonts/README.md` | New |
| `fonts/*.ttf` | JetBrains Mono 2.304 (Regular, Bold, Italic, Bold Italic) — SIL OFL 1.1 |
