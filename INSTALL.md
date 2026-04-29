# EDMD Installation Guide

EDMD is a Python daemon for real-time Elite Dangerous session monitoring. It supports three UI modes: a GTK4 graphical interface (Linux), a Textual terminal UI (all platforms), and an Electron desktop app (Windows, Linux, macOS).

---

## Windows

Download `EDMD-{version}-win.exe` from the [releases page](https://github.com/maldor/EDMD/releases) and run the installer. **No prerequisites are required.** Python 3.12, all Python dependencies, and the EDMD source are bundled inside the installer.

On first launch, EDMD creates a default `config.toml` at:

```
%APPDATA%\EDMD\config.toml
```

Open that file and set `JournalFolder` to your Elite Dangerous journal directory. The standard Windows location is:

```
C:\Users\YourName\Saved Games\Frontier Developments\Elite Dangerous
```

If EDMD cannot find your journal directory it will display a clear error with a button to open `config.toml` directly.

**Config and log files on Windows:**

| File | Location |
|------|----------|
| `config.toml` | `%APPDATA%\EDMD\config.toml` |
| `electron-launcher.log` | `%APPDATA%\EDMD\electron-launcher.log` |

The launcher log captures all startup activity and Python output. Check it first if EDMD fails to start.

---

## macOS

Download `EDMD-{version}-mac.dmg` from the [releases page](https://github.com/maldor/EDMD/releases). Drag EDMD to Applications and launch it.

Python 3.11+ must be installed separately (e.g. via [python.org](https://python.org) or Homebrew):

```bash
pip3 install websockets discord-webhook cryptography psutil
```

Config file location: `~/Library/Application Support/EDMD/config.toml`

---

## Linux — Arch

Arch ships current versions of everything EDMD needs.

```bash
sudo pacman -S python-psutil python-gobject gtk4
pip install discord-webhook cryptography --break-system-packages
```

```bash
git clone https://github.com/maldor/EDMD.git
cd EDMD
bash install.sh
nano ~/.local/share/EDMD/config.toml   # set JournalFolder at minimum

./edmd.py                    # terminal output only
./edmd.py --mode textual     # Textual TUI
./edmd.py --mode gtk4        # GTK4 GUI
```

---

## Linux — Debian / Ubuntu

```bash
sudo apt install python3-psutil python3-gi gir1.2-gtk-4.0
pip install discord-webhook cryptography --break-system-packages
```

```bash
git clone https://github.com/maldor/EDMD.git
cd EDMD
bash install.sh
nano ~/.local/share/EDMD/config.toml

./edmd.py
./edmd.py --mode textual
./edmd.py --mode gtk4
```

---

## Linux — Fedora

```bash
sudo dnf install python3-psutil python3-gobject gtk4
pip install discord-webhook cryptography --break-system-packages
```

---

## Electron GUI (Linux / macOS from source)

The Electron GUI is bundled in the Windows installer. On Linux and macOS it can be run from source alongside the Python backend:

```bash
pip install 'websockets>=12.0'
cd electron && npm install && npm run dev
```

For a packaged AppImage (Linux) or DMG (macOS), download the appropriate release artifact — Python must be installed on the system.

---

## Config file locations

| Platform | Path |
|----------|------|
| Windows  | `%APPDATA%\EDMD\config.toml` |
| Linux    | `~/.local/share/EDMD/config.toml` |
| macOS    | `~/Library/Application Support/EDMD/config.toml` |

On Linux, `~/.config/EDMD` is a symlink to `~/.local/share/EDMD/`. A repo-adjacent `config.toml` is accepted as a development fallback.

If no config file is found on startup, EDMD creates one with safe defaults and prints its location. Edit it to set `JournalFolder` before restarting.

---

## Dependencies

| Dependency | Purpose | Install method |
|------------|---------|----------------|
| `python-psutil` | Process utilities | Package manager (Linux) · pip (Windows/macOS) |
| `python-gobject` + `gtk4` | GTK4 GUI (Linux only) | Package manager only |
| `discord-webhook` | Discord notifications | pip |
| `cryptography` | CAPI auth and secure transport | pip |
| `websockets>=12.0` | Electron bridge | pip (bundled on Windows) |
| `textual>=0.47` | Textual TUI | pip (optional) |

> **Do not install `psutil` or `PyGObject` via pip on Linux.** They have C extensions that require system libraries only available through the distro package manager.

---

## Verifying a Linux install

```bash
python3 -c "import psutil, discord_webhook, cryptography; print('All dependencies OK')"
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'psutil'`**
Install via package manager: `sudo pacman -S python-psutil` (Arch) · `sudo apt install python3-psutil` (Debian/Ubuntu).

**`ModuleNotFoundError: No module named 'gi'`**
Install `python-gobject` (Arch) · `python3-gi` (Debian) · `python3-gobject` (Fedora), and GTK4 itself.

**`ModuleNotFoundError: No module named 'discord_webhook'`**
Run `pip install discord-webhook --break-system-packages`.

**`ModuleNotFoundError: No module named 'websockets'`**
Run `pip install 'websockets>=12.0' --break-system-packages`. On Windows this is bundled in the installer.

**JournalFolder not found (Electron on Windows)**
EDMD will show an error dialog with a button to open `config.toml`. Set `JournalFolder` to your ED journal directory and restart.

**EDMD fails to start on Windows — no error shown**
Open `%APPDATA%\EDMD\electron-launcher.log` in any text editor. All startup activity including Python errors is logged there.

**`GLib.GError` or blank GTK4 window**
Ensure `adwaita-icon-theme` (or equivalent) is installed.

**sshfs for remote access**
`sudo pacman -S sshfs` (Arch) · `sudo apt install sshfs` (Debian/Ubuntu) · `sudo dnf install fuse-sshfs` (Fedora). See [docs/guides/REMOTE_ACCESS.md](docs/guides/REMOTE_ACCESS.md).
