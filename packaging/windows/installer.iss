; Inno Setup script for AI SDLC Gate (Windows).
; Compiled by packaging/windows/build.ps1 after PyInstaller produces dist\ai-sdlc-gate.exe.
; Admin install: the exe goes under Local AppData and the policy under the user profile (where the git hooks
; look, $HOME\.ai-sdlc-gate). Admin is required so the git shim can be placed ahead of Git on the machine PATH
; for live --no-verify skip reporting. No git clone, no repository access required.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef RepoRoot
  #define RepoRoot "..\.."
#endif

[Setup]
AppId={{A1D5C0DE-5D1C-4A7E-9F00-A15D1CGATE01}}
AppName=AI SDLC Gate
AppVersion={#AppVersion}
AppPublisher=Otto Group One.O India
DefaultDirName={localappdata}\Programs\ai-sdlc-gate
DefaultGroupName=AI SDLC Gate
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir={#RepoRoot}\dist
OutputBaseFilename=ai-sdlc-gate-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes

[Files]
; The frozen engine.
Source: "{#RepoRoot}\dist\ai-sdlc-gate.exe"; DestDir: "{app}"; Flags: ignoreversion
; The skip-reporting shim enabler (self-validating; run during install, used again on uninstall).
Source: "{#RepoRoot}\packaging\windows\enable-shim.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Runtime policy laid where the hooks expect it: {userprofile}\.ai-sdlc-gate\repo and \hooks.
Source: "staging\repo\*";  DestDir: "{%USERPROFILE}\.ai-sdlc-gate\repo";  Flags: recursesubdirs createallsubdirs ignoreversion
Source: "staging\hooks\*"; DestDir: "{%USERPROFILE}\.ai-sdlc-gate\hooks"; Flags: recursesubdirs createallsubdirs ignoreversion

[Registry]
; Put the engine on the user PATH so `ai-sdlc-gate` resolves by name and the hooks find it.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}')

[Run]
; Point global git hooks at our hooks dir (Git for Windows runs them with bundled sh in every IDE/terminal).
Filename: "git"; Parameters: "config --global core.hooksPath ""{%USERPROFILE}/.ai-sdlc-gate/hooks"""; \
  Flags: runhidden; StatusMsg: "Installing git hooks..."
; Enable live --no-verify skip reporting: place the git shim ahead of Git on the machine PATH. Self-validating
; (rolls back if git breaks) and non-fatal to the rest of the install.
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""try {{ & '{app}\enable-shim.ps1' }} catch {{}} ; exit 0"""; \
  Flags: runhidden; StatusMsg: "Enabling skip reporting..."
; One-time Microsoft work-account sign-in, then prepare the review engine (uses the endpoint if policy sets one).
Filename: "{app}\ai-sdlc-gate.exe"; Parameters: "identity login --config ""{%USERPROFILE}\.ai-sdlc-gate\repo\gate.config.yaml"""; \
  Flags: postinstall runascurrentuser; Description: "Sign in with your Microsoft work account"
Filename: "{app}\ai-sdlc-gate.exe"; Parameters: "configure --config ""{%USERPROFILE}\.ai-sdlc-gate\repo\gate.config.yaml"""; \
  Flags: postinstall runascurrentuser; Description: "Prepare the review engine"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""try {{ & '{app}\enable-shim.ps1' -Disable }} catch {{}} ; exit 0"""; Flags: runhidden; RunOnceId: "RemoveShim"
Filename: "git"; Parameters: "config --global --unset core.hooksPath"; Flags: runhidden; RunOnceId: "UnsetHooks"

[Code]
function NeedsAddPath(Param: string): Boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + ExpandConstant(Param) + ';', ';' + OrigPath + ';') = 0;
end;
