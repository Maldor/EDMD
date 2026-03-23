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

1. **Checks for git.** Git is required to download the EDMD source and to apply
   future updates. If git is not found the installer warns you and links to
   [git-scm.com](https://git-scm.com/download/win). Install git first, then
   re-run the EDMD installer.

2. **Detects or installs MSYS2.** EDMD's GUI requires GTK4, which on Windows is
   provided by [MSYS2](https://msys2.org). The installer checks the standard
   locations (`C:\msys64`, `C:\msys2`, `%LOCALAPPDATA%\msys64`). If MSYS2 is
   not found it offers to download and install it silently (~100 MB, one-time).

3. **Installs GTK4 and Python.** Using MSYS2's `pacman` package manager, the
   installer installs:
   - `mingw-w64-ucrt-x86_64-gtk4`
   - `mingw-w64-ucrt-x86_64-python`
   - `mingw-w64-ucrt-x86_64-python-gobject`
   - `mingw-w64-ucrt-x86_64-python-psutil`
   - `mingw-w64-ucrt-x86_64-adwaita-icon-theme`

4. **Installs pip packages.** `discord-webhook` and `cryptography` are installed
   via MSYS2's pip.

5. **Clones the EDMD source.** The EDMD source code is cloned from GitHub into
   `%LOCALAPPDATA%\EDMD\src\` as a real git repository. This is what makes
   upgrade-in-place work.

6. **Installs EDMD.exe.** A small launcher executable is placed in
   `%LOCALAPPDATA%\EDMD\`. It locates MSYS2's Python and GTK4 libraries and
   launches `edmd.py` from the cloned source.

7. **Creates shortcuts.** Start Menu entries and an optional Desktop shortcut
   are created.

8. **Creates config.toml.** If no config exists, `example.config.toml` is
   copied to `%LOCALAPPDATA%\EDMD\config.toml`.

---

## After installation

Before running EDMD for the first time, edit your config file:

```
%LOCALAPPDATA%\EDMD\config.toml
```

Set `JournalFolder` to your Elite Dangerous journal path:

```toml
JournalFolder = "C:\\Users\\YourName\\Saved Games\\Frontier Developments\\Elite Dangerous"
```

Then launch EDMD from the Start Menu or Desktop shortcut.

---

## Updating EDMD

EDMD's installer sets up a live git repository. You can update at any time
from within the application:

```
EDMD.exe --upgrade
```

This runs `git pull` on the source, re-runs `install.bat`, and relaunches.
**Git must be on your PATH for this to work** — this is why the installer
requires git.

You can also re-run the full installer at any time. It will `git pull` if
a clone already exists rather than re-cloning from scratch.

---

## Upgrade from a previous manual installation

If you were previously running EDMD by cloning the repo yourself:

1. Run the new installer. It installs `EDMD.exe` and sets the `EDMD_SRC_DIR`
   environment variable to `%LOCALAPPDATA%\EDMD\src\`.
2. If you want to keep your existing clone, set `EDMD_SRC_DIR` to point to it:
   ```
   setx EDMD_SRC_DIR "C:\path\to\your\EDMD"
   ```
3. `EDMD.exe` will use your existing clone. Updates via `--upgrade` continue
   to work as before.

---

## Architecture

```
%LOCALAPPDATA%\EDMD\
    EDMD.exe          ← launcher (compiled, ~2 MB, no Python code inside)
    src\              ← full git clone of drworman/EDMD
        edmd.py
        core\
        builtins\
        gui\
        ...
    config.toml       ← your config (not overwritten by updates)

C:\msys64\            ← MSYS2 installation
    ucrt64\bin\
        python.exe    ← Python 3.12+
        gtk4\         ← GTK4 libraries
```

`EDMD.exe` is built with PyInstaller but contains **no EDMD Python code**.
It is purely a launcher that:
1. Locates MSYS2's `python.exe`
2. Prepends `C:\msys64\ucrt64\bin` to PATH (makes GTK4 DLLs visible)
3. Executes `python.exe src\edmd.py [your arguments]`

Because EDMD's Python code lives in a real git repo, `git pull` genuinely
updates it and `EDMD.exe` always runs the latest pulled version.

---

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `EDMD_MSYS2_ROOT` | Override MSYS2 search path | Auto-detected |
| `EDMD_SRC_DIR` | Override EDMD source directory | `%LOCALAPPDATA%\EDMD\src` |

Both are set automatically by the installer. Override them if your MSYS2 or
EDMD source lives in a non-standard location.

---

## Troubleshooting

**"MSYS2 not found" error when launching EDMD.exe**

EDMD.exe cannot locate `ucrt64\bin\python.exe` in any standard MSYS2 path.
Set `EDMD_MSYS2_ROOT` to your MSYS2 root:

```
setx EDMD_MSYS2_ROOT "D:\msys64"
```

Then relaunch EDMD.exe.

**GUI does not open / no window appears**

Check that GTK4 is installed in MSYS2:

```
C:\msys64\ucrt64\bin\python.exe -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; print('OK')"
```

If that fails, open the MSYS2 UCRT64 terminal and run:

```
pacman -S --needed mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-python-gobject
```

**"git not found" during --upgrade**

Add git to your PATH. From the Start Menu search for "Environment Variables",
find `Path` in User variables, and add the folder containing `git.exe`
(typically `C:\Program Files\Git\cmd`).

**Antivirus flags EDMD.exe**

PyInstaller executables are sometimes flagged by antivirus software because
they use the same extraction mechanism as some malware. EDMD.exe contains
only a Python launcher stub and can be inspected by building it yourself from
`edmd_launcher.spec`. If your AV blocks it, add an exception for
`%LOCALAPPDATA%\EDMD\EDMD.exe`.

---

## Building the installer yourself

Requirements:
- Windows 10/11 x64
- Python 3.11+ (standard Windows install)
- [PyInstaller](https://pyinstaller.org): `pip install pyinstaller`
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- git

```cmd
git clone https://github.com/drworman/EDMD.git
cd EDMD

:: Build the launcher exe
pyinstaller edmd_launcher.spec --noconfirm --clean

:: Build the installer (adjust path to your Inno Setup install)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\EDMD.iss
```

The installer will be at `dist\installer\EDMD-Setup-{version}.exe`.

The GitHub Actions workflow at `.github/workflows/windows-build.yml` does
this automatically on every release tag and attaches the result to the
GitHub Release.

---

## What is NOT bundled

- **EDMD Python source** — downloaded via git at install time; updated via `--upgrade`
- **GTK4** — installed via MSYS2 pacman; updated via `pacman -Syu` in MSYS2
- **Git** — must be installed separately; required for source download and updates
- **MSYS2** — downloaded and installed by the installer if not present (~100 MB)

This keeps the installer download small and ensures components are always
maintained through their native update channels.
