@echo off
setlocal EnableDelayedExpansion

:: fix_pip.bat — EDMD pip fix for existing installations
::
:: Calls MSYS2's Windows-native executables directly — no bash, no login
:: shell, no temp scripts. This avoids the MSYSTEM / PATH initialisation
:: issues that caused the previous version to fail on many machines.
::
:: Run as your normal user account — administrator is not required.
:: Double-click or run from a command prompt.

echo.
echo  EDMD pip fix
echo  ============
echo  Installs pip and all pip-managed EDMD packages into your MSYS2
echo  Python environment using MSYS2's native Windows executables.
echo.

:: ── Locate MSYS2 ─────────────────────────────────────────────────────────────

set "MSYS2_ROOT="

if defined EDMD_MSYS2_ROOT (
    if exist "%EDMD_MSYS2_ROOT%\ucrt64\bin\python.exe" (
        set "MSYS2_ROOT=%EDMD_MSYS2_ROOT%"
    )
)

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
            if exist "%%~D\ucrt64\bin\python.exe" (
                set "MSYS2_ROOT=%%~D"
            )
        )
    )
)

if not defined MSYS2_ROOT (
    echo  ERROR: Could not find MSYS2 with ucrt64\bin\python.exe.
    echo.
    echo  Checked:
    echo    %%EDMD_MSYS2_ROOT%%  (%EDMD_MSYS2_ROOT%)
    echo    C:\msys64, C:\msys2
    echo    %%LOCALAPPDATA%%\msys64 / msys2
    echo    %%ProgramFiles%%\msys64 / msys2
    echo.
    echo  If MSYS2 is installed elsewhere, set EDMD_MSYS2_ROOT:
    echo    setx EDMD_MSYS2_ROOT "D:\msys64"
    echo  Then re-run this script.
    echo.
    pause
    exit /b 1
)

set "PACMAN=%MSYS2_ROOT%\ucrt64\bin\pacman.exe"
set "PYTHON=%MSYS2_ROOT%\ucrt64\bin\python.exe"

echo  Found MSYS2 at: %MSYS2_ROOT%
echo  Using pacman:   %PACMAN%
echo  Using python:   %PYTHON%
echo.

:: ── Step 1: Install pip via pacman ───────────────────────────────────────────

echo  [1/3] Installing mingw-w64-ucrt-x86_64-python-pip via pacman...
echo.
"%PACMAN%" -S --needed --noconfirm mingw-w64-ucrt-x86_64-python-pip
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: pacman failed (exit code %ERRORLEVEL%).
    echo  This may be a transient network issue. Try again, or open
    echo  an MSYS2 UCRT64 terminal and run:
    echo    pacman -S mingw-w64-ucrt-x86_64-python-pip
    echo.
    pause
    exit /b 1
)
echo.
echo  pip installed.
echo.

:: ── Step 2: Upgrade pip ───────────────────────────────────────────────────────

echo  [2/3] Upgrading pip...
echo.
"%PYTHON%" -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo.
    echo  WARNING: pip self-upgrade failed. Continuing with installed pip version.
    echo.
)
echo.

:: ── Step 3: Install pip-managed EDMD packages ────────────────────────────────

echo  [3/3] Installing discord-webhook and cryptography...
echo.
"%PYTHON%" -m pip install "discord-webhook>=1.3.0" "cryptography>=41.0.0" "textual>=0.47.0"
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: pip install failed (exit code %ERRORLEVEL%).
    echo  Check the output above for details.
    echo.
    pause
    exit /b 1
)
echo.

:: ── Verify ───────────────────────────────────────────────────────────────────

echo  Verifying installed packages...
echo.

set "FAILED=0"

"%PYTHON%" -c "import discord_webhook; print('  discord-webhook  OK')"
if %ERRORLEVEL% neq 0 (
    echo   discord-webhook  FAILED
    set "FAILED=1"
)

"%PYTHON%" -c "import cryptography; print('  cryptography     OK')"
if %ERRORLEVEL% neq 0 (
    echo   cryptography     FAILED
    set "FAILED=1"
)

echo.
if "%FAILED%"=="0" (
    echo  All packages installed successfully.
    echo  Discord webhook posting and other pip-dependent features should
    echo  now work. Restart EDMD for the changes to take effect.
) else (
    echo  One or more packages failed the import check.
    echo  Try running this script again. If the problem persists, open an
    echo  MSYS2 UCRT64 terminal and run:
    echo    python -m pip install discord-webhook cryptography
)

echo.
pause
endlocal
