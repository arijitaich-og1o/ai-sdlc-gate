<#
.SYNOPSIS
  Build the self-contained Windows installer for AI SDLC Gate.

.DESCRIPTION
  1. creates a clean build venv and installs the engine + PyInstaller
  2. freezes the CLI into a single dist\ai-sdlc-gate.exe (bundled Python)
  3. stages the runtime policy (skills\, gate.config.yaml, client\hooks\) the installer ships
  4. compiles packaging\windows\installer.iss with Inno Setup (iscc) into an installer .exe

  Requires: Python 3.10+ and Inno Setup 6 (iscc.exe on PATH) on the build machine. Intended for the
  windows-latest GitHub Actions runner (see .github/workflows/build-windows.yml) but runs locally too.

.EXAMPLE
  pwsh packaging/windows/build.ps1
#>
[CmdletBinding()]
param(
  [string]$Version = "1.0.0"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$out  = Join-Path $repo "dist"
$stage = Join-Path $PSScriptRoot "staging"

Write-Host "== 1/4 build venv =="
$bvenv = Join-Path $env:TEMP "ai-sdlc-gate-build-venv"
if (Test-Path $bvenv) { Remove-Item -Recurse -Force $bvenv }
& py -3 -m venv $bvenv
$bpy = Join-Path $bvenv "Scripts\python.exe"
& $bpy -m pip install --quiet --upgrade pip wheel
& $bpy -m pip install --quiet (Join-Path $repo "gate") pyinstaller

Write-Host "== 2/4 freeze exe =="
Push-Location $PSScriptRoot
# PyInstaller logs to stderr; under $ErrorActionPreference='Stop' PowerShell 5.1 turns that into a terminating
# NativeCommandError. Relax it for this call and judge success by the exit code + the output file instead.
$eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
& $bpy -m PyInstaller --clean --noconfirm --log-level WARN --distpath $out "ai-sdlc-gate.spec" 2>&1 | ForEach-Object { "$_" }
$pyiExit = $LASTEXITCODE
$ErrorActionPreference = $eap
Pop-Location
if ($pyiExit -ne 0 -or -not (Test-Path (Join-Path $out "ai-sdlc-gate.exe"))) { throw "PyInstaller did not produce ai-sdlc-gate.exe (exit $pyiExit)" }

Write-Host "== 3/4 stage policy =="
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path (Join-Path $stage "repo") | Out-Null
Copy-Item -Recurse -Force (Join-Path $repo "skills")          (Join-Path $stage "repo\skills")
Copy-Item        -Force (Join-Path $repo "gate.config.yaml")   (Join-Path $stage "repo\gate.config.yaml")
Copy-Item -Recurse -Force (Join-Path $repo "client\hooks")    (Join-Path $stage "hooks")

Write-Host "== 4/4 compile installer =="
if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) { throw "Inno Setup (iscc.exe) not found on PATH" }
& iscc "/DAppVersion=$Version" "/DRepoRoot=$repo" (Join-Path $PSScriptRoot "installer.iss")
Write-Host "Done. Installer is in $out"
