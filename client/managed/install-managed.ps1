<#
.SYNOPSIS
  AI SDLC Gate — MANAGED client install for Windows (run as Administrator, typically via Intune / SCCM / GPO).

.DESCRIPTION
  Installs the gate where standard users cannot change it:
    C:\ProgramData\ai-sdlc-gate\repo     engine, skills, policy (Administrators: Full; Users: Read)
    C:\ProgramData\ai-sdlc-gate\venv     isolated Python with the ai-sdlc-gate CLI
    C:\ProgramData\ai-sdlc-gate\hooks    git hooks (bash, executed by Git for Windows' sh)
    C:\ProgramData\ai-sdlc-gate\bin      git.cmd shim (strips --no-verify / -n on commit, forces managed hooks path)
    system gitconfig                  core.hooksPath -> managed hooks; ai-sdlc-gate.managed=true (fail closed + identity required)
    Machine PATH                      C:\ProgramData\ai-sdlc-gate\bin is prepended so `git` resolves to the shim
    Scheduled task                    daily refresh of skills/policy as SYSTEM

  Each developer then runs `ai-sdlc-gate configure` (review configuration from the central repository) and `ai-sdlc-gate identity login`.
  Limits: local administrators can undo this. The GitHub ruleset is the guarantee; see docs/enforcement.md.
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = $(if ($env:AI_SDLC_GATE_REPO_URL) { $env:AI_SDLC_GATE_REPO_URL } else { "https://github.com/arijitaich-og1o/ai-sdlc-gate.git" }),
  [string]$Ref = $(if ($env:AI_SDLC_GATE_REF) { $env:AI_SDLC_GATE_REF } else { "main" }),
  [string]$Prefix = "C:\ProgramData\ai-sdlc-gate"
)
$ErrorActionPreference = "Stop"
function Say($m) { Write-Host "[ai-sdlc-gate] $m" -ForegroundColor Cyan }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Run as Administrator" }
$realGit = (Get-Command git.exe -ErrorAction Stop).Source
if ($realGit -like "$Prefix*") { $realGit = Get-Content (Join-Path $Prefix "bin\real-git.txt") }
$py = $null
foreach ($c in @("py -3", "python")) { try { $v = & cmd /c "$c -c ""import sys; print(sys.version_info >= (3,10))""" 2>$null; if ($v -match "True") { $py = $c; break } } catch {} }
if (-not $py) { throw "Python 3.10+ is required" }

New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "bin"), (Join-Path $Prefix "hooks") | Out-Null
$repo = Join-Path $Prefix "repo"
if (Test-Path (Join-Path $repo ".git")) { git -C $repo fetch --quiet --depth 1 origin $Ref; git -C $repo reset --quiet --hard FETCH_HEAD }
else { if (Test-Path $repo) { Remove-Item -Recurse -Force $repo }; git clone --quiet --depth 1 --branch $Ref $RepoUrl $repo }
Set-Content (Join-Path $Prefix "ref") $Ref -Encoding ascii

$venv = Join-Path $Prefix "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { & cmd /c "$py -m venv ""$venv""" }
& (Join-Path $venv "Scripts\python.exe") -m pip install --quiet --upgrade pip (Join-Path $repo "gate")
Copy-Item -Force (Join-Path $venv "Scripts\ai-sdlc-gate.exe") (Join-Path $Prefix "bin\ai-sdlc-gate.exe")

foreach ($h in @("commit-msg", "pre-push", "refresh-skills")) { Copy-Item -Force (Join-Path $repo "client\hooks\$h") (Join-Path $Prefix "hooks\$h") }

Set-Content (Join-Path $Prefix "bin\real-git.txt") $realGit -Encoding ascii
$shim = @"
@echo off
rem AI SDLC Gate managed git shim: forces the managed hooks path and removes hook-bypass flags.
setlocal EnableDelayedExpansion
set "GIT_CONFIG_PARAMETERS="
set "GIT_CONFIG_COUNT="
set "REALGIT=$realGit"
set "HOOKS=$($Prefix -replace '\\','/')/hooks"
set "ARGS="
set "SUB="
set "SKIPC=0"
:loop
if "%~1"=="" goto run
if "!SKIPC!"=="1" (
  set "SKIPC=0"
  echo %~1 | findstr /I /B "core.hooksPath core.hookspath ai-sdlc-gate." >nul && goto next
  set "ARGS=!ARGS! -c %1"
  goto next
)
if /I "%~1"=="-c" ( set "SKIPC=1" & goto next )
if "!SUB!"=="" (
  echo %~1 | findstr /B "-" >nul || set "SUB=%~1"
)
if /I "!SUB!"=="commit" (
  if /I "%~1"=="--no-verify" goto next
  if "%~1"=="-n" goto next
)
if /I "!SUB!"=="push" ( if /I "%~1"=="--no-verify" goto next )
if /I "!SUB!"=="merge" ( if /I "%~1"=="--no-verify" goto next )
set "ARGS=!ARGS! %1"
:next
shift
goto loop
:run
"%REALGIT%" -c core.hooksPath=%HOOKS% !ARGS!
exit /b %ERRORLEVEL%
"@
Set-Content (Join-Path $Prefix "bin\git.cmd") $shim -Encoding ascii

# ACLs: Administrators + SYSTEM full control, Users read/execute, no inheritance from ProgramData.
icacls $Prefix /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "Users:(OI)(CI)RX" | Out-Null

$hooksPosix = (Join-Path $Prefix "hooks") -replace "\\", "/"
git config --system core.hooksPath $hooksPosix
git config --system ai-sdlc-gate.managed true
git config --system ai-sdlc-gate.prefix ($Prefix -replace "\\", "/")

$binDir = Join-Path $Prefix "bin"
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
if ($machinePath -notlike "$binDir*") { [Environment]::SetEnvironmentVariable("Path", "$binDir;$machinePath", "Machine") }

$refresh = @"
`$ErrorActionPreference = 'Stop'
git -C '$repo' fetch --quiet --depth 1 origin (Get-Content '$Prefix\ref')
git -C '$repo' reset --quiet --hard FETCH_HEAD
& '$venv\Scripts\python.exe' -m pip install --quiet --upgrade '$repo\gate'
foreach (`$h in @('commit-msg','pre-push','refresh-skills')) { Copy-Item -Force "$repo\client\hooks\`$h" "$Prefix\hooks\`$h" }
"@
Set-Content (Join-Path $Prefix "bin\refresh-managed.ps1") $refresh -Encoding ascii
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Prefix\bin\refresh-managed.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At 03:15
Register-ScheduledTask -TaskName "AI SDLC Gate refresh" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest -Force | Out-Null

& (Join-Path $Prefix "bin\ai-sdlc-gate.exe") validate-skills --config (Join-Path $repo "gate.config.yaml")
Say "Managed install complete at $Prefix. Developers: run 'ai-sdlc-gate configure' and 'ai-sdlc-gate identity login'. Restart terminals/IDEs to pick up PATH."
