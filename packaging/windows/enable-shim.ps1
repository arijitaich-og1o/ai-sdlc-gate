<#
.SYNOPSIS
  Enable AI SDLC Gate skip-reporting on Windows (run as Administrator).

.DESCRIPTION
  Installs a tiny git shim ahead of Git for Windows on the machine PATH. A `git ... --no-verify` is then ALLOWED
  but reported to the organisation endpoint, so bypasses are tracked live. The shim changes no git arguments and
  always runs the real git.

  SAFE BY DESIGN: after installing, it runs `git --version` THROUGH the shim. If that does not work, it rolls the
  change back immediately (restores PATH, removes the shim) and stops — so it can never leave git broken.

  Undo at any time:  powershell -ExecutionPolicy Bypass -File enable-shim.ps1 -Disable

.EXAMPLE
  # From an elevated PowerShell:
  powershell -ExecutionPolicy Bypass -File enable-shim.ps1
#>
[CmdletBinding()]
param([switch]$Disable)

$ErrorActionPreference = "Stop"
$ShimDir = Join-Path $env:ProgramData "ai-sdlc-gate\bin"
$ShimCmd = Join-Path $ShimDir "git.cmd"

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Please run this in an elevated PowerShell (Run as Administrator). Git for Windows is on the machine PATH, which only an admin can get ahead of."
  }
}

function Remove-FromMachinePath([string]$dir) {
  $mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $kept = ($mp -split ';' | Where-Object { $_ -and ($_.TrimEnd('\') -ne $dir.TrimEnd('\')) }) -join ';'
  [Environment]::SetEnvironmentVariable("Path", $kept, "Machine")
}

if ($Disable) {
  Assert-Admin
  Remove-FromMachinePath $ShimDir
  if (Test-Path $ShimDir) { Remove-Item $ShimDir -Recurse -Force }
  Write-Host "AI SDLC Gate git shim removed. Open a new terminal; git is back to normal." -ForegroundColor Green
  return
}

Assert-Admin
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw "Git for Windows was not found on PATH." }
if (-not (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue)) {
  # Not fatal: when run from the installer the PATH isn't refreshed yet, and the shim resolves `ai-sdlc-gate`
  # by name at run time (from a new terminal), so this is only informational.
  Write-Host "Note: 'ai-sdlc-gate' is not on the current PATH yet; the shim resolves it by name when you run git from a new terminal." -ForegroundColor Yellow
}

# The shim: scan (read-only) for --no-verify, report it in the background, then run the REAL git with the
# original args unchanged. On any problem it still runs the real git.
$shim = @'
@echo off
set "_AISDLC_REALGIT="
for /f "delims=" %%G in ('where git.exe 2^>nul') do if not defined _AISDLC_REALGIT set "_AISDLC_REALGIT=%%G"
if not defined _AISDLC_REALGIT set "_AISDLC_REALGIT=git.exe"
set "_AISDLC_BYPASS="
:aisdlc_scan
if "%~1"=="" goto aisdlc_done
if /I "%~1"=="--no-verify" set "_AISDLC_BYPASS=1"
shift
goto aisdlc_scan
:aisdlc_done
if defined _AISDLC_BYPASS start "" /b ai-sdlc-gate report-skip --config "%USERPROFILE%\.ai-sdlc-gate\repo\gate.config.yaml" --command "no-verify" >nul 2>&1
"%_AISDLC_REALGIT%" %*
exit /b %ERRORLEVEL%
'@

$prevPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
New-Item -ItemType Directory -Force -Path $ShimDir | Out-Null
Set-Content -Path $ShimCmd -Value $shim -Encoding ascii
if (($prevPath -split ';') -notcontains $ShimDir) {
  [Environment]::SetEnvironmentVariable("Path", "$ShimDir;$prevPath", "Machine")
}

# SELF-TEST: resolve git through the shim dir and confirm it still works. Roll back on any failure.
$env:Path = "$ShimDir;$env:Path"
$ok = $false
try { $ok = ((& cmd /c "`"$ShimCmd`" --version" 2>&1) -match "git version") } catch { $ok = $false }
if (-not $ok) {
  [Environment]::SetEnvironmentVariable("Path", $prevPath, "Machine")
  if (Test-Path $ShimDir) { Remove-Item $ShimDir -Recurse -Force }
  throw "Shim self-test failed (git did not run through the shim). Rolled back; git is untouched."
}

Write-Host "AI SDLC Gate: skip-reporting enabled and verified." -ForegroundColor Green
Write-Host "Open a NEW terminal, then any 'git ... --no-verify' will be reported (and still allowed)." -ForegroundColor Green
Write-Host "To undo: run this script again with -Disable." -ForegroundColor Yellow
