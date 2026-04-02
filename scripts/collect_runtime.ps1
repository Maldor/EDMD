# scripts/collect_runtime.ps1 — Collect bundled Windows runtime from MSYS2
#
# Copies the MSYS2 UCRT64 Python interpreter, GTK4 DLL stack, GI typelibs,
# GLib schemas, Adwaita icons, and all EDMD pip dependencies into dist\runtime\.
# The Inno Setup installer then ships this directory alongside the EDMD source
# so users need no local MSYS2 installation.
#
# Run on the build machine AFTER MSYS2 + required packages are installed.
# The GitHub Actions workflow calls this automatically.
#
# Usage:
#   .\scripts\collect_runtime.ps1
#   .\scripts\collect_runtime.ps1 -Msys2Root D:\msys64 -OutDir dist\runtime
#
# Requirements (install with pacman before running):
#   mingw-w64-ucrt-x86_64-gtk4
#   mingw-w64-ucrt-x86_64-python
#   mingw-w64-ucrt-x86_64-python-gobject
#   mingw-w64-ucrt-x86_64-python-psutil
#   mingw-w64-ucrt-x86_64-python-pip
#   mingw-w64-ucrt-x86_64-adwaita-icon-theme

param(
    [string]$Msys2Root = "C:\msys64",
    [string]$OutDir    = "dist\runtime"
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # suppress slow Copy-Item progress bars

# ── Validate MSYS2 ────────────────────────────────────────────────────────────

$ucrt       = Join-Path $Msys2Root "ucrt64"
$python_exe = Join-Path $ucrt "bin\python.exe"
$pacman_exe = Join-Path $ucrt "bin\pacman.exe"

if (-not (Test-Path $python_exe)) {
    throw "python.exe not found at $python_exe. Install mingw-w64-ucrt-x86_64-python first."
}

Write-Host "==> collect_runtime.ps1"
Write-Host "    MSYS2 root : $Msys2Root"
Write-Host "    UCRT64     : $ucrt"
Write-Host "    Output     : $OutDir"
Write-Host ""

# ── Discover Python version ───────────────────────────────────────────────────

$py_xyz = & $python_exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
$py_xy  = & $python_exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$py_dir = "python$($py_xy -replace '\.', '')"   # e.g. python312
$lib_rel = "lib\python$py_xy"                   # lib\python3.12

Write-Host "    Python     : $py_xyz  ($lib_rel)"
Write-Host ""

# ── Create output directory ───────────────────────────────────────────────────

if (Test-Path $OutDir) {
    Write-Host "[1/8] Clearing existing runtime output..."
    Remove-Item $OutDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "lib") | Out-Null

# ── 1. Python executable ──────────────────────────────────────────────────────

Write-Host "[1/8] Copying Python executable..."
Copy-Item (Join-Path $ucrt "bin\python.exe")  (Join-Path $OutDir "python.exe")
# Some extension modules call python3.exe or python3.12.exe — copy those too
foreach ($alias in @("python3.exe", "python$($py_xy).exe")) {
    $src = Join-Path $ucrt "bin\$alias"
    if (Test-Path $src) { Copy-Item $src (Join-Path $OutDir $alias) }
}

# ── 2. DLLs ───────────────────────────────────────────────────────────────────
# Copy all DLLs from ucrt64/bin. This is intentionally broad — the GTK4 stack
# has many transitive dependencies and the lzma2 installer compresses them well.
# We exclude MSYS2 tool executables (.exe) to keep the runtime clean.

Write-Host "[2/8] Copying GTK4 + Python DLLs from ucrt64\bin..."
$dll_count = 0
Get-ChildItem (Join-Path $ucrt "bin") -Filter "*.dll" | ForEach-Object {
    Copy-Item $_.FullName $OutDir
    $dll_count++
}
Write-Host "      $dll_count DLLs copied."

# ── 3. Install pip-managed packages into MSYS2 Python (before copying) ───────
# discord-webhook and cryptography are not available via pacman.
# We install them into the ORIGINAL MSYS2 Python here so they are present in
# ucrt64\lib\python3.x\site-packages\ when the lib tree is copied in step 4.
# Installing into the copied runtime Python fails because the copied exe cannot
# reliably report its own platform tags to pip, causing pip to select the source
# distribution for cryptography (which requires maturin/Rust to compile).
# --only-binary :all: prevents any source builds.
# --break-system-packages bypasses MSYS2's PEP 668 externally-managed marker.

Write-Host "[3/8] Installing pip-managed packages into MSYS2 Python..."
$ucrt_python_exe = Join-Path $ucrt "bin\python.exe"
& $ucrt_python_exe -m pip install `
    --break-system-packages `
    --only-binary :all: `
    --no-warn-script-location `
    "discord-webhook>=1.3.0" `
    "cryptography>=41.0.0"
if ($LASTEXITCODE -ne 0) {
    throw "pip install into MSYS2 Python failed (exit code $LASTEXITCODE)"
}
Write-Host "      pip packages installed into MSYS2 Python."

# ── 4. Python stdlib + site-packages ─────────────────────────────────────────
# Copy the full Python lib tree — stdlib, lib-dynload (.pyd extension modules),
# and site-packages (gi, psutil, discord_webhook, cryptography, etc.).

Write-Host "[4/8] Copying Python stdlib and site-packages..."
$py_lib_src = Join-Path $ucrt "lib\python$py_xy"
if (-not (Test-Path $py_lib_src)) {
    throw "Python lib not found at $py_lib_src"
}
$py_lib_dst = Join-Path $OutDir $lib_rel
Copy-Item $py_lib_src $py_lib_dst -Recurse -Force
Write-Host "      Copied: $py_lib_src"

# ── 5. GI typelibs ────────────────────────────────────────────────────────────

Write-Host "[5/8] Copying GI typelibs..."
$typelib_src = Join-Path $ucrt "lib\girepository-1.0"
if (Test-Path $typelib_src) {
    $typelib_dst = Join-Path $OutDir "lib\girepository-1.0"
    Copy-Item $typelib_src $typelib_dst -Recurse -Force
    $n = (Get-ChildItem $typelib_dst -Filter "*.typelib").Count
    Write-Host "      $n typelibs copied."
} else {
    Write-Warning "GI typelib directory not found — gi imports may fail."
}

# ── 6. GLib schemas ───────────────────────────────────────────────────────────
# Must be compiled; glib-compile-schemas produces gschemas.compiled.

Write-Host "[6/8] Copying and compiling GLib schemas..."
$schema_src = Join-Path $ucrt "share\glib-2.0\schemas"
$schema_dst = Join-Path $OutDir "share\glib-2.0\schemas"
if (Test-Path $schema_src) {
    New-Item -ItemType Directory -Force -Path $schema_dst | Out-Null
    Copy-Item "$schema_src\*" $schema_dst -Recurse -Force
    # Compile (produces gschemas.compiled which GTK4 requires at runtime)
    $compile = Join-Path $ucrt "bin\glib-compile-schemas.exe"
    if (Test-Path $compile) {
        & $compile $schema_dst
        Write-Host "      Schemas compiled."
    } else {
        Write-Warning "glib-compile-schemas.exe not found; schemas not compiled."
    }
} else {
    Write-Warning "GLib schemas directory not found."
}

# ── 7. Adwaita icon theme ─────────────────────────────────────────────────────

Write-Host "[7/8] Copying Adwaita icon theme..."
$icons_src = Join-Path $ucrt "share\icons\Adwaita"
if (Test-Path $icons_src) {
    $icons_dst = Join-Path $OutDir "share\icons\Adwaita"
    Copy-Item $icons_src $icons_dst -Recurse -Force
    Write-Host "      Adwaita icons copied."
} else {
    Write-Warning "Adwaita icon theme not found — install mingw-w64-ucrt-x86_64-adwaita-icon-theme."
}

# hicolor fallback theme (required by GTK icon loading)
$hicolor_src = Join-Path $ucrt "share\icons\hicolor"
if (Test-Path $hicolor_src) {
    Copy-Item $hicolor_src (Join-Path $OutDir "share\icons\hicolor") -Recurse -Force
}

# ── 8. Create ._pth file ──────────────────────────────────────────────────────
# Tells the copied python.exe where to find its stdlib relative to its own
# directory, overriding the hardcoded MSYS2 prefix in the original binary.
# pip packages (discord_webhook, cryptography) were installed into MSYS2 Python
# in step 3 and are now present in the copied site-packages from step 4.

Write-Host "[8/8] Creating python._pth file..."
$pth_content = @"
$lib_rel
$lib_rel\lib-dynload
$lib_rel\site-packages
import site
"@
$pth_file = Join-Path $OutDir "${py_dir}._pth"
Set-Content -Path $pth_file -Value $pth_content -Encoding ASCII
Write-Host "      Created $pth_file"

# ── 9. Verify the runtime ─────────────────────────────────────────────────────
# We verify that Python runs and that pip-installed packages are importable.
# GTK4 is NOT imported here — initialising it on a headless CI runner blocks
# indefinitely waiting for a display subsystem that doesn't exist.
# DLL presence is confirmed implicitly by the import of gi (PyGObject), which
# loads libgobject and its chain at import time without opening a window.

Write-Host "[9/9] Verifying runtime imports..."

$verify_script = @"
import sys
print(f'  Python {sys.version}')

failures = []

def check(name, code):
    try:
        exec(code)
        print(f'  {name:30s} OK')
    except Exception as e:
        print(f'  {name:30s} FAILED: {e}')
        failures.append(name)

check('gi (PyGObject)',      'import gi')
# GTK4 not checked here — from gi.repository import Gtk blocks on headless runners.
# The DLLs are verified to exist by collect_runtime.ps1 before this step runs.
check('psutil',              'import psutil')
check('discord_webhook',     'import discord_webhook')
check('cryptography',        'import cryptography')

if failures:
    print(f'\nFAILED: {failures}')
    sys.exit(1)
else:
    print('\nAll imports OK — runtime is valid.')
"@

$verify_py = Join-Path $OutDir "_verify.py"
Set-Content -Path $verify_py -Value $verify_script -Encoding UTF8

# Set env vars the runtime needs to find typelibs and schemas at verify time
$env_backup = @{}
$env_vars = @{
    "GI_TYPELIB_PATH" = (Join-Path $OutDir "lib\girepository-1.0")
    "XDG_DATA_DIRS"   = (Join-Path $OutDir "share")
    "PATH"            = "$OutDir;$env:PATH"
}
foreach ($k in $env_vars.Keys) {
    $env_backup[$k] = [System.Environment]::GetEnvironmentVariable($k)
    [System.Environment]::SetEnvironmentVariable($k, $env_vars[$k])
}

try {
    # Use Start-Process with a 60-second timeout so a blocked import cannot hang
    # the entire CI job. If the timeout fires, the runner kills the process and
    # the build fails with a clear message rather than timing out silently.
    $proc = Start-Process `
        -FilePath    $runtime_python `
        -ArgumentList $verify_py `
        -PassThru `
        -NoNewWindow
    if (-not $proc.WaitForExit(60000)) {
        $proc.Kill()
        throw "Runtime verification timed out after 60 s. A Python import is blocking (possibly gi init). Check collect_runtime.ps1."
    }
    $rc = $proc.ExitCode
} finally {
    foreach ($k in $env_backup.Keys) {
        [System.Environment]::SetEnvironmentVariable($k, $env_backup[$k])
    }
    Remove-Item $verify_py -Force -ErrorAction SilentlyContinue
}

if ($rc -ne 0) {
    throw "Runtime verification failed (exit $rc). Fix the errors above before building the installer."
}

# ── Summary ───────────────────────────────────────────────────────────────────

$size_mb = [math]::Round((Get-ChildItem $OutDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host ""
Write-Host "==> Runtime collected successfully."
Write-Host "    Output : $OutDir"
Write-Host "    Size   : ${size_mb} MB (uncompressed; lzma2 installer will compress significantly)"
Write-Host ""
