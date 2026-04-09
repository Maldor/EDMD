# EDMD Installation Guide

EDMD is a Python daemon for real-time Elite Dangerous AFK session monitoring.

---

## Dependencies

EDMD has two types of dependencies:

**System packages** (install via your package manager — do NOT use pip for these on Linux):
- `python-psutil` — process and system utilities
- `python-gobject` + `gtk4` — GTK4 GUI support (Linux; optional)

**pip packages:**
- `discord-webhook` — Discord notification support
- `cryptography` — config integrity verification and secure transport features

---

## Linux — Arch

Arch ships current versions of everything EDMD needs.

```bash
sudo pacman -S python-psutil python-gobject gtk4
pip install discord-webhook cryptography --break-system-packages
```

**Running EDMD:**

```bash
git clone https://github.com/drworman/EDMD.git
cd EDMD
bash install.sh         # creates ~/.local/share/EDMD/config.toml from example
nano ~/.local/share/EDMD/config.toml   # set JournalFolder at minimum
./edmd.py
./edmd.py --gui         # GTK4 interface
```

---

## Linux — Debian / Ubuntu

```bash
sudo apt install python3-psutil python3-gi gir1.2-gtk-4.0
pip install discord-webhook cryptography --break-system-packages
```

**Running EDMD:**

```bash
git clone https://github.com/drworman/EDMD.git
cd EDMD
bash install.sh
nano ~/.local/share/EDMD/config.toml
./edmd.py --gui
```

---

## Linux — Fedora

```bash
sudo dnf install python3-psutil python3-gobject gtk4
pip install discord-webhook cryptography --break-system-packages
```

---

## Windows

Download **`EDMD-Setup-{version}.exe`** from the [latest release](https://github.com/drworman/EDMD/releases/latest).

The installer is fully self-contained — it ships a bundled Python + GTK4 runtime and requires **no MSYS2 installation** on your machine. The only external requirement is [Git for Windows](https://git-scm.com/download/win) for downloading the EDMD source and future updates; the installer will offer to install git automatically if it is not found.

See **[docs/guides/WINDOWS_INSTALLER.md](docs/guides/WINDOWS_INSTALLER.md)** for full details.

> **Developer notice:** EDMD is developed and tested on Linux. Windows support is best-effort — the developer cannot provide direct troubleshooting for Windows-specific issues.

---

## Config file location

`install.sh` creates `config.toml` in the EDMD user data directory automatically.
If you need to locate or create it manually:

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/EDMD/config.toml` |
| Windows | `%APPDATA%\EDMD\config.toml` |

On Linux, `~/.config/EDMD` is a symlink to `~/.local/share/EDMD/` — you can use
either path. A repo-adjacent `config.toml` is also accepted as a fallback for
development or portable installs.

---

## Fonts

EDMD bundles **JetBrains Mono** in the `fonts/` directory of the repo. On first launch, EDMD copies those TTF files into `~/.local/share/EDMD/fonts/` (its own data directory) and registers them with Pango for the current process — no system font directories are touched and no font cache rebuild is required. On Windows the data directory is `%APPDATA%\EDMD\fonts\`.

Any installed monospace font can be selected from **Settings → Appearance → Font Family** in the GUI. Font size is adjustable there as well (10–24 px). Both settings require a restart to take effect.

If the `fonts/` directory is empty (e.g. a git clone without the font files), EDMD falls back silently to the system monospace font. To obtain the bundled fonts, download the four TTF files from the [JetBrains Mono releases page](https://github.com/JetBrains/JetBrainsMono/releases/latest) and place them in `fonts/`:

- `JetBrainsMono-Regular.ttf`
- `JetBrainsMono-Bold.ttf`
- `JetBrainsMono-Italic.ttf`
- `JetBrainsMono-BoldItalic.ttf`

---

## Verifying your install

```bash
python3 -c "import psutil, discord_webhook, cryptography; print('All dependencies OK')"
```

---

## GTK4 GUI

The GUI requires PyGObject with GTK4 bindings. If these are not available EDMD falls back to terminal mode automatically:

```bash
./edmd.py    # terminal mode — always works, no GUI dependencies
./edmd.py --gui  # GTK4 GUI mode
```

| Platform | GUI support | How to get GTK4 |
|---|---|---|
| Linux | ✅ First-class | System package manager — see distro sections above |
| Windows | ⚠️ Experimental | Installer — see [WINDOWS_INSTALLER.md](docs/guides/WINDOWS_INSTALLER.md) |

GTK4 availability is checked at runtime — if `--gui` is passed but PyGObject cannot be loaded, EDMD prints a clear error and falls back to terminal mode.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'psutil'`**
Install via your package manager, not pip: `sudo pacman -S python-psutil` (Arch) or `sudo apt install python3-psutil` (Debian/Ubuntu).

**`ModuleNotFoundError: No module named 'gi'`**
PyGObject is not installed. Install `python-gobject` (Arch), `python3-gi` (Debian), or `python3-gobject` (Fedora). GTK4 itself must also be installed.

**`ModuleNotFoundError: No module named 'discord_webhook'`**
Run `pip install discord-webhook --break-system-packages`.

**`ModuleNotFoundError: No module named 'cryptography'`**
Run `pip install cryptography --break-system-packages`.

**`sshfs` for remote access**
If you plan to use EDMD's remote GUI mode (secondary machine as thin client), install `sshfs` on the secondary machine:
`sudo pacman -S sshfs` (Arch) · `sudo apt install sshfs` (Debian/Ubuntu) · `sudo dnf install fuse-sshfs` (Fedora).
See [docs/guides/REMOTE_ACCESS.md](docs/guides/REMOTE_ACCESS.md) for full setup.

**`GLib.GError` or blank GUI window**
Your GTK4 theme or icon set may be incomplete. Ensure `adwaita-icon-theme` (or equivalent) is installed for your distro.

**auto-quit doesn't trigger / antivirus warning**
EDMD uses `psutil` to exit `EliteDangerous64.exe` under certain conditions. Some antivirus tools flag process-termination behaviour. If EDMD is blocked, add an exclusion for the EDMD folder in your antivirus settings.
