@echo off
setlocal EnableDelayedExpansion

:: fix_pip.bat — EDMD pip fix for existing installations
::
:: Installs mingw-w64-ucrt-x86_64-python-pip via pacman, then
:: installs all pip-managed EDMD dependencies (discord-webhook,
:: cryptography) that may have failed during the original setup.
::
:: Run as your normal user account — administrator is not required.
:: Double-click to run, or launch from a command prompt.

echo.
echo  EDMD pip fix
echo  ============
echo  This script installs pip into your MSYS2 Python environment
echo  and pulls in all pip-managed EDMD dependencies.
echo.

:: ── Locate MSYS2 ─────────────────────────────────────────────────────────────

set "MSYS2_ROOT="

:: Check environment variable set by the EDMD installer first
if defined EDMD_MSYS2_ROOT (
    if exist "%EDMD_MSYS2_ROOT%\usr\bin\bash.exe" (
        set "MSYS2_ROOT=%EDMD_MSYS2_ROOT%"
    )
)

:: Fall back to common install locations
if not defined MSYS2_ROOT (
    for %%D in (
        "C:\msys64"
        "C:\msys2"
        "%LOCALAPPDATA%\msys64"
        "%LOCALAPPDATA%\msys2"
        "%ProgramFiles%\msys64"
        "%ProgramFiles%\msys2"
    ) do (
        if not defined MSYS2_ROOT (
            if exist "%%~D\usr\bin\bash.exe" (
                set "MSYS2_ROOT=%%~D"
            )
        )
    )
)

if not defined MSYS2_ROOT (
    echo  ERROR: MSYS2 not found.
    echo.
    echo  Checked:
    echo    %%EDMD_MSYS2_ROOT%%
    echo    C:\msys64
    echo    C:\msys2
    echo    %%LOCALAPPDATA%%\msys64 / msys2
    echo    %%ProgramFiles%%\msys64 / msys2
    echo.
    echo  If MSYS2 is installed in a non-standard location, set the
    echo  EDMD_MSYS2_ROOT environment variable to its root path and
    echo  re-run this script.
    echo.
    pause
    exit /b 1
)

echo  Found MSYS2 at: %MSYS2_ROOT%
echo.

:: ── Write the fix script ──────────────────────────────────────────────────────

set "SCRIPT=%MSYS2_ROOT%\edmd_fix_pip.sh"

(
    echo #!/usr/bin/env bash
    echo set -euo pipefail
    echo.
    echo log^(^) { echo "[EDMD fix] $*"; }
    echo.
    echo export PATH="/ucrt64/bin:${PATH}"
    echo.
    echo # ── Step 1: install pip via pacman ──────────────────────────────────
    echo log "Installing mingw-w64-ucrt-x86_64-python-pip via pacman..."
    echo pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-python-pip
    echo log "pip installed."
    echo.
    echo # ── Step 2: upgrade pip itself ───────────────────────────────────────
    echo log "Upgrading pip..."
    echo python -m pip install --upgrade pip
    echo.
    echo # ── Step 3: install pip-managed EDMD dependencies ────────────────────
    echo log "Installing discord-webhook and cryptography..."
    echo python -m pip install "discord-webhook>=1.3.0" "cryptography>=41.0.0"
    echo.
    echo # ── Step 4: verify ───────────────────────────────────────────────────
    echo FAILED=0
    echo.
    echo if python -c "import discord_webhook" 2^>/dev/null; then
    echo     log "  discord-webhook  OK"
    echo else
    echo     log "  discord-webhook  FAILED"
    echo     FAILED=1
    echo fi
    echo.
    echo if python -c "import cryptography" 2^>/dev/null; then
    echo     log "  cryptography     OK"
    echo else
    echo     log "  cryptography     FAILED"
    echo     FAILED=1
    echo fi
    echo.
    echo if [ "$FAILED" -eq 0 ]; then
    echo     log "All packages installed successfully. Discord webhook posting should now work."
    echo else
    echo     log "One or more packages failed to install. Check the output above for errors."
    echo     exit 1
    echo fi
) > "%SCRIPT%"

:: ── Run it via MSYS2 bash ─────────────────────────────────────────────────────

echo  Running fix script via MSYS2 bash...
echo  (pacman and pip output will appear below)
echo.

set MSYSTEM=UCRT64
"%MSYS2_ROOT%\usr\bin\bash.exe" --login -c "/edmd_fix_pip.sh"
set "RC=%ERRORLEVEL%"

:: Clean up the temp script
del "%SCRIPT%" 2>nul

echo.
if "%RC%"=="0" (
    echo  Done. Restart EDMD for the changes to take effect.
) else (
    echo  Fix did not complete cleanly (exit code %RC%).
    echo  Check the output above. If pacman failed, try running
    echo  this script again — a partial download may have caused
    echo  a transient error.
)

echo.
pause
endlocal
