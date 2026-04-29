## EDMD v20260411

### Electron GUI — Windows & macOS (first stable release)

This release ships a fully self-contained Electron desktop app for Windows, Linux, and macOS. The Windows installer bundles Python 3.12 and all required dependencies — no prerequisites required.

#### Windows installer
- Python 3.12 embeddable, `websockets`, `discord-webhook`, `cryptography`, and `psutil` are bundled inside the `.exe`. Install and launch — nothing else needed.
- Data directory is now correctly `%APPDATA%\EDMD\` on Windows, matching all previous releases.
- A diagnostic log is written to `%APPDATA%\EDMD\electron-launcher.log` on every launch. Check this first if EDMD fails to start.

#### Startup error handling
- If EDMD cannot start, a clear error screen is shown explaining exactly what went wrong — journal directory not found, Python dependency missing, or unexpected crash.
- The error screen includes buttons to open `config.toml` directly in your system editor, view the diagnostic log, and open Preferences.
- Specific failure reasons are written to `%APPDATA%\EDMD\electron-error.json` by the Python backend before exiting, so Electron can surface the exact message rather than a generic timeout.

#### Auto-generated config
- If no `config.toml` is found on startup, EDMD creates one with safe defaults at the platform data directory and continues. The path is printed on startup. Edit `JournalFolder` and restart.

#### Preferences — Setup tab
- New Setup tab in Preferences for configuring the path to `edmd.py`, Python interpreter, launch profile (`-p`), and extra CLI arguments — all saved persistently across sessions.
- Startup errors auto-open Preferences to the Setup tab.

#### Theme support
- Theme selection in Preferences now takes effect immediately in the Electron renderer. All eight built-in themes are supported: default (orange), green, blue, purple, red, yellow, dark, and light.

#### Reports
- Reports menu in the title bar now correctly maps to all eight available reports: Career Overview, Bounty Breakdown, Session History, Hunting Grounds, NPC Rogues' Gallery, Exploration, Exobiology, and PowerPlay.
- Reports were previously broken due to a missing handler — fixed.

#### Preferences restart
- Saving preferences that require a restart (e.g. theme change, journal folder change) now automatically respawns the Python backend and reloads the renderer. No manual quit and relaunch required.

#### CI / release pipeline
- GitHub Actions workflow produces signed release artifacts for Linux (AppImage + deb), Windows (NSIS installer), and macOS (DMG).
- SSH signatures (`.sig`) and a unified `SHA-256` checksum file are generated for all artifacts.
- Workflow now validates bundled Python presence and installer size before uploading.

### Platform data directory corrections

| Platform | Correct path |
|----------|-------------|
| Windows  | `%APPDATA%\EDMD\` |
| Linux    | `~/.local/share/EDMD/` |
| macOS    | `~/Library/Application Support/EDMD/` |

Previous Windows builds incorrectly used `.local\share\EDMD\` — this caused EDMD to be unable to find an existing `config.toml` on Windows. Fixed in `core/state.py`.

### False idle alert fix (from 20260410)
`activity_combat.py` had an independent idle timer (`_last_summary_mono`) that was set once at load time and never refreshed. This caused spurious inactive-session alerts during long sessions. The timer is now reset on every quarter-hour summary via an `on_summary()` hook on `ActivityProviderMixin`.

---

**Full changelog:** see commit history on the `electron` branch.
**Verification:** download `EDMD-20260411.sha256` and the corresponding `.sha256.sig` and verify with `ssh-keygen -Y verify`.
