# EDMD Windows Installer

> **Developer notice:** EDMD is developed and tested on Linux.
> The Windows installer is best-effort. Terminal mode works on Windows with no
> special setup. The GUI requires GTK4, which the installer handles automatically.

---

## Download

Download `EDMD-Setup-{version}.exe` from the
[latest release](https://github.com/drworman/EDMD/releases/latest).

---

## What the installer does

1. **Checks for Git.** Git is required to download the EDMD source and apply
   future updates. If git is not found the installer offers to download and
   install Git for Windows silently (~60 MB).

2. **Installs the bundled runtime.** The installer ships a self-contained
   `runtime\` directory containing Python 3.12, GTK4 and all its dependency
   DLLs, PyGObject, psutil, discord-webhook, cryptography, GI typelibs,
   compiled GLib schemas, and the Adwaita icon theme.
   **No MSYS2, no pacman, no internet connection required at install time.**

3. **Clones the EDMD source** from GitHub into `%LOCALAPPDATA%\EDMD\src\`
   as a real git repository, enabling upgrade-in-place.

4. **Installs EDMD.exe.** A small launcher stub placed in
   `%LOCALAPPDATA%\EDMD\` that finds `runtime\python.exe` and launches
   `src\edmd.py`.

5. **Creates shortcuts** and **copies config.toml** if none exists.

---

## After installation

Edit your config file before first launch:

```
%APPDATA%\EDMD\config.toml
```

Set `JournalFolder` to your Elite Dangerous journal directory:

```toml
JournalFolder = "C:/Users/YourName/Saved Games/Frontier Developments/Elite Dangerous"
```

Use forward slashes or double backslashes — single backslashes cause a
TOML parse error.

---

## Updating EDMD

```
EDMD.exe --upgrade
```

This runs `git pull` on the source and relaunches. To update the bundled
runtime (GTK4, Python, pip packages), re-run the full installer.

---

## Architecture

```
%LOCALAPPDATA%\EDMD\
    EDMD.exe          -- launcher stub (~2 MB, no Python code inside)
    runtime\          -- self-contained Python + GTK4 runtime
        python.exe
        python312._pth
        lib\python3.12\site-packages\   (gi, psutil, discord_webhook, cryptography)
        lib\girepository-1.0\           (GI typelibs)
        share\glib-2.0\schemas\         (compiled GLib schemas)
        share\icons\Adwaita\            (icon theme)
        libgtk-4-1.dll, ...             (GTK4 + 100+ dependency DLLs)
    src\              -- git clone of drworman/EDMD
        edmd.py, core\, builtins\, gui\, ...

%APPDATA%\EDMD\
    config.toml       -- your config (never overwritten by updates)
```

`EDMD.exe` is a pure launcher: finds `runtime\python.exe`, sets PATH and
GTK4 environment variables, and executes `src\edmd.py`. Falls back to any
MSYS2 UCRT64 Python installation for developer machines and older installs.

---

## Troubleshooting

**"Source not found" error**
Re-run the installer, or: `git clone --depth=1 https://github.com/drworman/EDMD.git %LOCALAPPDATA%\EDMD\src`

**"Python runtime not found" error**
Re-run the installer to restore `runtime\`.

**GUI does not open**
```cmd
%LOCALAPPDATA%\EDMD\runtime\python.exe -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; print('OK')"
```
If this fails, re-run the installer.

**"git not found" during --upgrade**
Add `C:\Program Files\Git\cmd` to your PATH via Environment Variables in
System Properties.

**Antivirus flags EDMD.exe**
EDMD.exe is a PyInstaller-compiled launcher stub. Add an exception for
`%LOCALAPPDATA%\EDMD\EDMD.exe`, or build it yourself from `edmd_launcher.spec`.

---

## Building the installer yourself

Requirements: Python 3.11+ · PyInstaller · Inno Setup 6 · MSYS2 (build machine only) · Git

```powershell
git clone https://github.com/drworman/EDMD.git && cd EDMD

# Build launcher
pyinstaller edmd_launcher.spec --noconfirm --clean

# Install MSYS2 packages on build machine (one-time):
# pacman -S mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-python
#           mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-python-psutil
#           mingw-w64-ucrt-x86_64-python-pip mingw-w64-ucrt-x86_64-adwaita-icon-theme
#           mingw-w64-ucrt-x86_64-glib-compile-schemas

# Collect bundled runtime
.\scripts\collect_runtime.ps1 -Msys2Root C:\msys64 -OutDir dist\runtime

# Build installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\EDMD.iss
```

The GitHub Actions workflow at `.github/workflows/windows-build.yml` does
this automatically on every release tag.
