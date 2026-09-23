<#
  AI SDLC Gate zero-prerequisite bootstrap (Windows).

  Ensures Python 3.10+ and Git are present for the CURRENT USER (no administrator rights), installing them if
  missing, then runs the normal installer. Everything happens in this one PowerShell process so the freshly
  installed tools are on PATH for the steps that follow. A bundled gate.record beside this file is imported by the
  installer, so a tester double-clicks and everything installs with nothing pre-required but an internet connection.
#>
$ErrorActionPreference = "Stop"
function Say($m) { Write-Host "[ai-sdlc-gate] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[ai-sdlc-gate] $m" -ForegroundColor Yellow }

$PY_URL  = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
$GIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-64-bit.7z.exe"
$home_   = Join-Path $env:USERPROFILE ".ai-sdlc-gate"
$tools   = Join-Path $home_ "tools"
$ProgressPreference = "SilentlyContinue"   # faster, quieter Invoke-WebRequest

# Carry a bundled review configuration through to the installer (imported instead of the key broker).
if (-not $env:AI_SDLC_GATE_RECORD_FILE) {
  $rec = Join-Path $PSScriptRoot "gate.record"
  if (Test-Path $rec) { $env:AI_SDLC_GATE_RECORD_FILE = $rec }
}

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Test-Python {
  foreach ($c in @("py -3", "python", "python3")) {
    try { $v = & cmd /c "$c -c ""import sys; print(sys.version_info >= (3,10))""" 2>$null; if ($v -match "True") { return $true } } catch {}
  }
  return $false
}

# ---------------------------------------------------------------- Python (per-user, no admin)
if (Test-Python) {
  Say "Python 3.10+ found."
} else {
  Say "Installing Python 3.12 for your user (one-time, no administrator needed)..."
  $exe = Join-Path $env:TEMP "ai-sdlc-python-3.12.7.exe"
  try {
    Invoke-WebRequest $PY_URL -OutFile $exe
    # InstallAllUsers=0 -> per-user (no elevation). PrependPath adds it to PATH. Include pip and the py launcher.
    $p = Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_launcher=1" -Wait -PassThru
    Refresh-Path
  } catch { Warn "Automatic Python install failed: $($_.Exception.Message)" }
  if (-not (Test-Python)) {
    Warn "Could not install Python automatically. Install Python 3.10+ from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH') and run this again."
    Read-Host "Press Enter to close"; exit 1
  }
  Say "Python installed."
}

# ---------------------------------------------------------------- Git (portable, no admin)
if (Get-Command git.exe -ErrorAction SilentlyContinue) {
  Say "Git found."
} else {
  Say "Installing a portable Git for your user (one-time, no administrator needed)..."
  $gitDir = Join-Path $tools "git"
  New-Item -ItemType Directory -Force -Path $gitDir | Out-Null
  $exe = Join-Path $env:TEMP "ai-sdlc-PortableGit.7z.exe"
  try {
    Invoke-WebRequest $GIT_URL -OutFile $exe
    # Self-extracting 7z: -o<dir> extracts, -y accepts. No installation, no elevation.
    Start-Process $exe -ArgumentList "-o`"$gitDir`" -y" -Wait
    $gitCmd = Join-Path $gitDir "cmd"
    $env:Path = "$gitCmd;$env:Path"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$gitCmd*") { [Environment]::SetEnvironmentVariable("Path", "$gitCmd;$userPath", "User") }
  } catch { Warn "Automatic Git install failed: $($_.Exception.Message)" }
  if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Warn "Could not install Git automatically. Install Git for Windows from https://git-scm.com/download/win and run this again."
    Read-Host "Press Enter to close"; exit 1
  }
  Say "Git installed."
}

# ---------------------------------------------------------------- run the installer from the public repository
$repo = Join-Path $home_ "repo"
if (-not (Test-Path (Join-Path $repo ".git"))) {
  Say "Downloading the AI SDLC Gate..."
  git clone --quiet --depth 1 https://github.com/arijitaich-og1o/ai-sdlc-gate $repo
}
& (Join-Path $repo "client\install.ps1")
