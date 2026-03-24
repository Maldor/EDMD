; EDMD.iss — Inno Setup installer script for Elite Dangerous Monitor Daemon
; https://github.com/drworman/EDMD
;
; Build requirements:
;   Inno Setup 6.x          https://jrsoftware.org/isinfo.php
;   EDMD.exe launcher       built by edmd_launcher.spec (PyInstaller)
;   Git for Windows         https://git-scm.com  (detected at runtime, not bundled)
;
; What this installer does:
;   1.  Detects or installs MSYS2 (UCR T64) silently
;   2.  Installs GTK4 + PyGObject + psutil via pacman
;   3.  Installs discord-webhook + cryptography via MSYS2 pip
;   4.  Clones (or updates) the EDMD source via git into {localappdata}\EDMD\src
;   5.  Copies EDMD.exe launcher to {localappdata}\EDMD
;   6.  Creates Start Menu entry and optional Desktop shortcut
;
; Upgrade behaviour:
;   Re-running the installer clones/pulls the latest source.
;   Users can also run "EDMD.exe --upgrade" at any time.

#define AppName      "EDMD"
#define AppVersion   "20260323"
#define AppPublisher "CMDR CALURSUS"
#define AppURL       "https://github.com/drworman/EDMD"
#define AppExeName   "EDMD.exe"
#define AppSrcRepo   "https://github.com/drworman/EDMD.git"
#define MSYS2URL     "https://github.com/msys2/msys2-installer/releases/download/nightly-x86_64/msys2-x86_64-latest.exe"
#define MSYS2SHA256  ""   ; set if you pin a specific release for security

[Setup]
AppId               = {{A3F2B1C4-8E6D-4F2A-9B1C-D5E7F3A2B4C6}
AppName             = {#AppName}
AppVersion          = {#AppVersion}
AppPublisherURL     = {#AppURL}
AppSupportURL       = {#AppURL}/issues
AppUpdatesURL       = {#AppURL}/releases
DefaultDirName      = {localappdata}\EDMD
DefaultGroupName    = EDMD
DisableProgramGroupPage = yes
OutputDir           = ..\dist\installer
OutputBaseFilename  = EDMD-Setup-{#AppVersion}
Compression         = lzma2/ultra64
SolidCompression    = yes
WizardStyle         = modern
PrivilegesRequired  = lowest
PrivilegesRequiredOverridesAllowed = dialog
ArchitecturesInstallIn64BitMode    = x64compatible
UninstallDisplayIcon= {app}\{#AppExeName}
ChangesEnvironment  = yes
SetupLogging        = yes

; Minimum Windows 10
MinVersion = 10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; EDMD.exe launcher (built by PyInstaller — no EDMD source inside)
Source: "..\dist\EDMD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation (optional convenience copies)
Source: "..\README.md";             DestDir: "{app}";      Flags: ignoreversion
Source: "..\INSTALL.md";            DestDir: "{app}";      Flags: ignoreversion
Source: "..\docs\*";                DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";                     Filename: "{app}\{#AppExeName}"; Comment: "Elite Dangerous Monitor Daemon"
Name: "{group}\{#AppName} (terminal mode)";     Filename: "{app}\{#AppExeName}"; Parameters: "--no-gui"; Comment: "EDMD without the GTK4 GUI"
Name: "{group}\Uninstall {#AppName}";           Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";               Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Step 1: Clone or update EDMD source using Windows-native git.
; Runs independently of MSYS2 so it cannot be blocked by GTK4 setup.
Filename: "{code:GetGitExe}"; \
  Parameters: "{code:GetGitParams}"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Downloading EDMD source..."; \
  Flags: waituntilterminated runhidden

; Step 2: Install GTK4, Python, and pip packages via MSYS2 bash.
Filename: "{code:GetMsys2Root}\usr\bin\bash.exe"; \
  Parameters: "--login -c ""{code:GetEdmdSetupScript}"""; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installing GTK4 and Python packages..."; \
  Flags: waituntilterminated runhidden

[UninstallDelete]
; Remove the source clone and any generated files on uninstall
Type: filesandordirs; Name: "{app}\src"
Type: filesandordirs; Name: "{app}\logs"

[Code]
//
// Pascal scripting — handles:
//   - Git availability check
//   - MSYS2 detection and silent install
//   - Generating the setup bash script path
//

var
  Msys2Root:     String;
  GitAvailable:  Boolean;

// ── Helpers ────────────────────────────────────────────────────────────────

function FindMsys2(): String;
var
  Candidates: TArrayOfString;
  LocalApp:   String;
  ProgFiles:  String;
  I:          Integer;
begin
  Result := '';
  LocalApp := ExpandConstant('{localappdata}');
  ProgFiles := ExpandConstant('{pf64}');

  SetArrayLength(Candidates, 6);
  Candidates[0] := 'C:\msys64';
  Candidates[1] := 'C:\msys2';
  Candidates[2] := LocalApp + '\msys64';
  Candidates[3] := LocalApp + '\msys2';
  Candidates[4] := ProgFiles + '\msys64';
  Candidates[5] := ProgFiles + '\msys2';

  for I := 0 to GetArrayLength(Candidates) - 1 do
  begin
    // Check for usr\bin\bash.exe which exists after base MSYS2 install.
    // ucrt64\bin\python.exe only exists after pacman installs it, so
    // it cannot be used as the detection marker.
    if FileExists(Candidates[I] + '\usr\bin\bash.exe') then
    begin
      Result := Candidates[I];
      Exit;
    end;
  end;
end;

function GitFound(): Boolean;
var
  ResultCode:  Integer;
  InstallPath: String;
begin
  // 1. Check PATH (works if git was already installed before this process started)
  if Exec('cmd.exe', '/c where git >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
     and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;
  // 2. Check registry — Git for Windows writes InstallPath here even
  //    when the PATH update hasn't been picked up by the current process
  if RegQueryStringValue(HKLM, 'SOFTWARE\GitForWindows', 'InstallPath', InstallPath) then
  begin
    if FileExists(InstallPath + '\cmd\git.exe') then
    begin
      Result := True;
      Exit;
    end;
  end;
  if RegQueryStringValue(HKCU, 'SOFTWARE\GitForWindows', 'InstallPath', InstallPath) then
  begin
    if FileExists(InstallPath + '\cmd\git.exe') then
    begin
      Result := True;
      Exit;
    end;
  end;
  // 3. Check the two default install paths Git for Windows uses
  if FileExists(ExpandConstant('{pf64}') + '\Git\cmd\git.exe') then
  begin
    Result := True;
    Exit;
  end;
  if FileExists(ExpandConstant('{localappdata}') + '\Programs\Git\cmd\git.exe') then
  begin
    Result := True;
    Exit;
  end;
  Result := False;
end;

// ── InitializeSetup ────────────────────────────────────────────────────────

function InitializeSetup(): Boolean;
var
  Answer: Integer;
begin
  Result := True;

  // Check git
  GitAvailable := GitFound();
  if not GitAvailable then
  begin
    Answer := MsgBox(
      'Git was not found on your PATH.' + #13#10 + #13#10 +
      'EDMD uses git to download its source files and to apply updates ' +
      '("EDMD.exe --upgrade").' + #13#10 + #13#10 +
      'You can install Git for Windows from:' + #13#10 +
      '  https://git-scm.com/download/win' + #13#10 + #13#10 +
      'Install git now, then re-run this installer.' + #13#10 + #13#10 +
      'Continue anyway without git? (EDMD will not be able to download ' +
      'its source files and will not run.)',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2
    );
    if Answer = IDNO then
    begin
      Result := False;
      Exit;
    end;
  end;

  // Check / locate MSYS2
  Msys2Root := FindMsys2();
end;

// ── NextButtonClick ────────────────────────────────────────────────────────

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
  MSYS2Installer: String;
  DownloadPage: TDownloadWizardPage;
begin
  Result := True;

  // On the "Ready to install" page, install MSYS2 if not found
  if (CurPageID = wpReady) and (Msys2Root = '') then
  begin
    if MsgBox(
      'MSYS2 was not found on this computer.' + #13#10 + #13#10 +
      'EDMD requires MSYS2 (UCRT64) with GTK4 for its graphical interface.' + #13#10 + #13#10 +
      'The installer will now download and install MSYS2 (~100 MB).' + #13#10 +
      'This is a one-time step. MSYS2 is a standard development environment ' +
      'for GTK4 on Windows.' + #13#10 + #13#10 +
      'Install MSYS2 now?',
      mbConfirmation, MB_YESNO
    ) = IDNO then
    begin
      MsgBox(
        'MSYS2 is required for EDMD''s GUI mode.' + #13#10 +
        'Without it, only terminal mode will work (edmd.py via Python directly).' + #13#10 + #13#10 +
        'You can install MSYS2 later from https://msys2.org and re-run this installer.',
        mbInformation, MB_OK
      );
      // Allow install to continue — terminal mode will still be available
    end else begin
      MSYS2Installer := ExpandConstant('{tmp}\msys2-installer.exe');

      DownloadPage := CreateDownloadPage(
        'Downloading MSYS2',
        'Downloading MSYS2 package manager and build environment...',
        nil
      );
      DownloadPage.Clear;
      DownloadPage.Add('{#MSYS2URL}', 'msys2-installer.exe', '');
      DownloadPage.Show;
      try
        try
          DownloadPage.Download;
        except
          MsgBox('Download failed: ' + GetExceptionMessage + #13#10 +
                 'Please install MSYS2 manually from https://msys2.org',
                 mbError, MB_OK);
          Result := False;
          Exit;
        end;
      finally
        DownloadPage.Hide;
      end;

      // Run MSYS2 installer silently — installs to C:\msys64 by default
      WizardForm.StatusLabel.Caption := 'Installing MSYS2...';
      Exec(MSYS2Installer,
           'in --confirm-command --accept-messages --root C:\msys64',
           '', SW_SHOW, ewWaitUntilTerminated, ResultCode);

      Msys2Root := FindMsys2();
      if Msys2Root = '' then
      begin
        MsgBox('MSYS2 installation did not complete as expected.' + #13#10 +
               'Please install MSYS2 manually from https://msys2.org and re-run this installer.',
               mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;
  end;
end;

// ── Code functions used in [Run] section ──────────────────────────────────

function GetGitExe(Param: String): String;
var
  InstallPath: String;
begin
  if RegQueryStringValue(HKLM, 'SOFTWARE\GitForWindows', 'InstallPath', InstallPath) then
    if FileExists(InstallPath + '\cmd\git.exe') then
    begin Result := InstallPath + '\cmd\git.exe'; Exit; end;
  if RegQueryStringValue(HKCU, 'SOFTWARE\GitForWindows', 'InstallPath', InstallPath) then
    if FileExists(InstallPath + '\cmd\git.exe') then
    begin Result := InstallPath + '\cmd\git.exe'; Exit; end;
  if FileExists(ExpandConstant('{pf64}') + '\Git\cmd\git.exe') then
  begin Result := ExpandConstant('{pf64}') + '\Git\cmd\git.exe'; Exit; end;
  if FileExists(ExpandConstant('{localappdata}') + '\Programs\Git\cmd\git.exe') then
  begin Result := ExpandConstant('{localappdata}') + '\Programs\Git\cmd\git.exe'; Exit; end;
  Result := 'git.exe';
end;

function GetGitParams(Param: String): String;
var
  SrcDir: String;
begin
  SrcDir := ExpandConstant('{app}') + '\src';
  if DirExists(SrcDir + '\.git') then
    Result := '-C "' + SrcDir + '" pull --ff-only'
  else
    Result := 'clone --depth=1 https://github.com/drworman/EDMD.git "' + SrcDir + '"';
end;

function GetMsys2Root(Param: String): String;
begin
  if Msys2Root = '' then
    Result := 'C:\msys64'   // fallback — bash will fail gracefully if absent
  else
    Result := Msys2Root;
end;

function GetEdmdSetupScript(Param: String): String;
// Returns an inline bash script that:
//   1. Updates pacman db
//   2. Installs GTK4, PyGObject, python, psutil
//   3. Installs pip packages (discord-webhook, cryptography)
//   4. Clones or pulls the EDMD source
//   5. Copies example.config.toml if no config exists
var
  AppDir: String;
  SrcDir: String;
  CfgDir: String;
begin
  AppDir := ExpandConstant('{app}');
  SrcDir := AppDir + '\src';
  CfgDir := ExpandConstant('{localappdata}') + '\EDMD';

  // Escape backslashes for bash; wrap the whole thing in quotes for Inno
  // We write a temp script file instead to avoid quoting nightmares
  Result := '/edmd_setup.sh';   // written by CurStepChanged below
end;

// ── CurStepChanged — write the setup script before [Run] executes ─────────

function WinPathToBash(S: String): String;
var
  I: Integer;
begin
  Result := S;
  for I := 1 to Length(Result) do
    if Result[I] = chr(92) then Result[I] := chr(47);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ScriptPath: String;
  Script:     TStringList;
  AppDir:     String;
  SrcDir:     String;
  CfgDir:     String;
  Ms2Root:    String;
begin
  if CurStep <> ssPostInstall then Exit;

  AppDir  := ExpandConstant('{app}');
  SrcDir  := AppDir + '\src';
  CfgDir  := ExpandConstant('{localappdata}') + '\EDMD';
  Ms2Root := GetMsys2Root('');

  // Convert Windows paths to MSYS2 paths (C:\foo → /c/foo)
  // Inno cannot run bash natively so we write the script to the MSYS2 root
  ScriptPath := Ms2Root + '\edmd_setup.sh';

  Script := TStringList.Create;
  try
    Script.Add('#!/usr/bin/env bash');
    Script.Add('set -euo pipefail');
    Script.Add('');
    Script.Add('# EDMD post-install setup script');
    Script.Add('# Generated by the EDMD installer — do not edit by hand.');
    Script.Add('');
    Script.Add('MSYS2_ROOT="' + WinPathToBash(Ms2Root) + '"');
    Script.Add('EDMD_APP="' + WinPathToBash(AppDir) + '"');
    Script.Add('EDMD_SRC="' + WinPathToBash(SrcDir) + '"');
    Script.Add('EDMD_CFG="' + WinPathToBash(CfgDir) + '"');
    Script.Add('');
    Script.Add('log() { echo "[EDMD] $*"; }');
    Script.Add('');
    Script.Add('# ── 1. Initialise pacman keyring (MSYS2 first-run) ───────────────');
    Script.Add('log "Initialising MSYS2..."');
    Script.Add('pacman-key --init 2>/dev/null || true');
    Script.Add('pacman-key --populate 2>/dev/null || true');
    Script.Add('');
    Script.Add('# ── 2. Update package database ──────────────────────────────────');
    Script.Add('log "Updating package database..."');
    Script.Add('pacman -Sy --noconfirm 2>/dev/null || true');
    Script.Add('');
    Script.Add('# ── 3. Install GTK4 + Python stack ─────────────────────────────');
    Script.Add('log "Installing GTK4, PyGObject, Python, psutil..."');
    Script.Add('PKGS=(');
    Script.Add('    mingw-w64-ucrt-x86_64-gtk4');
    Script.Add('    mingw-w64-ucrt-x86_64-python');
    Script.Add('    mingw-w64-ucrt-x86_64-python-gobject');
    Script.Add('    mingw-w64-ucrt-x86_64-python-psutil');
    Script.Add('    mingw-w64-ucrt-x86_64-adwaita-icon-theme');
    Script.Add(')');
    Script.Add('pacman -S --needed --noconfirm "${PKGS[@]}"');
    Script.Add('log "GTK4 stack installed."');
    Script.Add('');
    Script.Add('# ── 4. pip packages ─────────────────────────────────────────────');
    Script.Add('log "Installing pip packages..."');
    Script.Add('PYTHON="${MSYS2_ROOT}/ucrt64/bin/python.exe"');
    Script.Add('"${PYTHON}" -m pip install --quiet --upgrade pip 2>/dev/null || true');
    Script.Add('"${PYTHON}" -m pip install --quiet "discord-webhook>=1.3.0" "cryptography>=41.0.0"');
    Script.Add('log "pip packages installed."');
    Script.Add('');
    Script.Add('# ── 5. Config file ───────────────────────────────────────────────');
    Script.Add('# Note: git clone/pull is handled by the Windows-native git step.');
    Script.Add('mkdir -p "${EDMD_CFG}"');
    Script.Add('if [ ! -f "${EDMD_CFG}/config.toml" ]; then');
    Script.Add('    if [ -f "${EDMD_SRC}/example.config.toml" ]; then');
    Script.Add('        cp "${EDMD_SRC}/example.config.toml" "${EDMD_CFG}/config.toml"');
    Script.Add('        log "Created config.toml — edit JournalFolder before running EDMD."');
    Script.Add('    fi');
    Script.Add('fi');
    Script.Add('');
    Script.Add('log "EDMD setup complete."');

    Script.SaveToFile(ScriptPath);
  finally
    Script.Free;
  end;

  // Set EDMD_MSYS2_ROOT in the user environment so EDMD.exe finds MSYS2
  if Ms2Root <> '' then
    RegWriteStringValue(HKCU, 'Environment', 'EDMD_MSYS2_ROOT', Ms2Root);

  // Also set EDMD_SRC_DIR so the launcher finds the source
  RegWriteStringValue(HKCU, 'Environment', 'EDMD_SRC_DIR', SrcDir);
end;

// ── Uninstall cleanup ──────────────────────────────────────────────────────

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKCU, 'Environment', 'EDMD_MSYS2_ROOT');
    RegDeleteValue(HKCU, 'Environment', 'EDMD_SRC_DIR');
  end;
end;