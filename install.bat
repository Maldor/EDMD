@echo off
setlocal enabledelayedexpansion
title EDMD Installer

:: =============================================================================
:: EDMD — install.bat
:: Windows installer for ED Monitor Daemon
:: https://github.com/drworman/EDMD
:: =============================================================================

echo.
echo   ███████╗██████╗ ███╗   ███╗██████╗
echo   ██╔════╝██╔══██╗████╗ ████║██╔══██╗
echo   █████╗  ██║  ██║██╔████╔██║██║  ██║
echo   ██╔══╝  ██║  ██║██║╚██╔╝██║██║  ██║
echo   ███████╗██████╔╝██║ ╚═╝ ██║██████╔╝
echo   ╚══════╝╚═════╝ ╚═╝     ╚═╝╚═════╝
echo.
echo   ED Monitor Daemon -- Windows Installer
echo   https://github.com/drworman/EDMD
echo.

:: ── Python check ──────────────────────────────────────────────────────────────
echo [EDMD] Checking Python...

set PYTHON_CMD=
for %%P in (python python3 py) do (
    where %%P >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%V in ('%%P --version 2^>^&1') do (
            set PYVER=%%V
        )
        set PYTHON_CMD=%%P
        goto :found_python
    )
)

echo [ FAIL ] Python not found.
echo.
echo   Please install Python 3.11 or newer from https://python.org
echo   Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found_python
echo [  OK  ] Found Python %PYVER% at %PYTHON_CMD%

:: Check minimum version
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    set PY_MAJOR=%%A
    set PY_MINOR=%%B
)
if %PY_MAJOR% LSS 3 goto :python_too_old
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 goto :python_too_old
goto :python_ok

:python_too_old
echo [ FAIL ] Python %PYVER% is too old. EDMD requires Python 3.11+.
echo.
echo   Download from: https://python.org/downloads
echo.
pause
exit /b 1

:python_ok

:: ── pip check ─────────────────────────────────────────────────────────────────
echo [EDMD] Checking pip...
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ WARN ] pip not found. Attempting to install...
    %PYTHON_CMD% -m ensurepip --upgrade
    if errorlevel 1 (
        echo [ FAIL ] Could not install pip. Please install it manually.
        pause
        exit /b 1
    )
)
echo [  OK  ] pip is available

:: ── Install pip packages ───────────────────────────────────────────────────────
echo.
echo -- Installing pip packages --

echo [EDMD] Installing psutil...
%PYTHON_CMD% -m pip install "psutil>=5.9.0" --quiet
if errorlevel 1 (
    echo [ WARN ] psutil install failed. Retry manually: pip install psutil
) else (
    echo [  OK  ] psutil installed
)

echo [EDMD] Installing discord-webhook...
%PYTHON_CMD% -m pip install "discord-webhook>=1.3.0" --quiet
if errorlevel 1 (
    echo [ WARN ] discord-webhook install failed. Retry manually: pip install discord-webhook
    echo [ WARN ] Discord notifications will be unavailable until resolved.
) else (
    echo [  OK  ] discord-webhook installed
)

echo [EDMD] Installing cryptography...
%PYTHON_CMD% -m pip install "cryptography>=41.0.0" --quiet
if errorlevel 1 (
    echo [ WARN ] cryptography install failed. Retry manually: pip install cryptography
) else (
    echo [  OK  ] cryptography installed
)

:: ── GUI note ──────────────────────────────────────────────────────────────────
echo.
echo -- GUI mode on Windows --
echo.
echo [ INFO ] GTK4 GUI mode on Windows requires additional setup beyond this
echo [ INFO ] installer. Two approaches are available -- see:
echo.
echo     docs\guides\WINDOWS_GUI.md
echo.
echo [ INFO ] Option A (MSYS2):  run install_msys2.sh inside the MSYS2 UCRT64 terminal.
echo [ INFO ] Option B (gvsbuild): build GTK4 natively, then run install_gvsbuild.bat.
echo.
echo [ INFO ] Terminal mode installed by this script is fully functional --
echo [ INFO ] all monitoring, Discord alerts, and reporting work without the GUI.
echo [ INFO ] The GUI is an optional enhancement.

:: ── Config setup ──────────────────────────────────────────────────────────────
echo.
echo -- Configuration --

if not exist "%~dp0config.toml" (
    if exist "%~dp0example.config.toml" (
        copy "%~dp0example.config.toml" "%~dp0config.toml" >nul
        echo [  OK  ] Created config.toml from example
    ) else (
        echo [ WARN ] No config.toml found. Create it before running EDMD.
    )
) else (
    echo [  OK  ] config.toml already exists -- leaving untouched
)

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo -- Installation complete --
echo.
echo   EDMD is ready to run in terminal mode.
echo.
echo   Run in terminal:
echo     python edmd.py
echo.
echo   With a config profile:
echo     python edmd.py -p YourProfileName
echo.
echo   For optional GTK4 GUI support on Windows, see:
echo     docs\guides\WINDOWS_GUI.md
echo.
echo   Edit config.toml to set your journal folder before running:
echo     JournalFolder = "C:\Users\YourName\Saved Games\Frontier Developments\Elite Dangerous"
echo.
echo   See INSTALL.md and README.md for full documentation.
echo.
pause
