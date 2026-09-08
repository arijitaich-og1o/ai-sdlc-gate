<#
.SYNOPSIS
  AI SDLC Gate developer installer for Windows (PowerShell 5.1+ / 7+, with Git for Windows).

.DESCRIPTION
  1. clones (or refreshes) the central repository to %USERPROFILE%\.ai-sdlc-gate\repo
  2. installs the `ai-sdlc-gate` CLI for the current user (pipx if available, else pip --user)
  3. installs global git hooks (commit-msg, pre-push) via core.hooksPath. Git for Windows runs hooks with its
     bundled sh, so the same bash hooks work in PowerShell, cmd, VS Code, IntelliJ and any other IDE.
  4. obtains the review configuration from the central repository (key broker) and keeps it in Windows Credential Manager
  5. signs the developer in with their Microsoft work account (one-time)

.EXAMPLE
  irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = $(if ($env:AI_SDLC_GATE_REPO_URL) { $env:AI_SDLC_GATE_REPO_URL } else { "https://github.com/arijitaich-og1o/ai-sdlc-gate.git" }),
  [string]$Ref = $(if ($env:AI_SDLC_GATE_REF) { $env:AI_SDLC_GATE_REF } else { "main" })
)

$ErrorActionPreference = "Stop"
function Say($m) { Write-Host "[ai-sdlc-gate] $m" -ForegroundColor Cyan }
function Die($m) { Write-Host "[ai-sdlc-gate] $m" -ForegroundColor Red; exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git is required (Git for Windows)" }
$py = $null
foreach ($c in @("py -3", "python", "python3")) {
  try {
    $v = & cmd /c "$c -c ""import sys; print(sys.version_info >= (3,10))""" 2>$null
    if ($v -match "True") { $py = $c; break }
  } catch {}
}
if (-not $py) { Die "Python 3.10+ is required" }

$home_ = if ($env:AI_SDLC_GATE_HOME) { $env:AI_SDLC_GATE_HOME } else { Join-Path $env:USERPROFILE ".ai-sdlc-gate" }
$repo = Join-Path $home_ "repo"
$hooks = Join-Path $home_ "hooks"
New-Item -ItemType Directory -Force -Path $hooks | Out-Null

Say "Syncing central repository ($Ref) to $repo"
if (Test-Path (Join-Path $repo ".git")) {
  git -C $repo fetch --quiet --depth 1 origin $Ref
  git -C $repo reset --quiet --hard FETCH_HEAD
} else {
  if (Test-Path $repo) { Remove-Item -Recurse -Force $repo }
  git clone --quiet --depth 1 --branch $Ref $RepoUrl $repo
}
Set-Content -Path (Join-Path $home_ "ref") -Value $Ref -Encoding ascii

Say "Installing the ai-sdlc-gate CLI"
if (Get-Command pipx -ErrorAction SilentlyContinue) {
  pipx install --force --quiet (Join-Path $repo "gate") | Out-Null
} else {
  & cmd /c "$py -m pip install --quiet --user --upgrade ""$(Join-Path $repo 'gate')"""
  $scripts = & cmd /c "$py -c ""import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"""
  if ($scripts -and -not (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue)) {
    Say "Adding $scripts to the user PATH (restart your terminal/IDE afterwards)"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$scripts*") { [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User") }
    $env:Path = "$env:Path;$scripts"
  }
}

Say "Installing global git hooks"
foreach ($h in @("commit-msg", "pre-push", "refresh-skills")) {
  Copy-Item -Force (Join-Path $repo "client\hooks\$h") (Join-Path $hooks $h)
}
$hooksPosix = $hooks -replace "\\", "/"
$current = git config --global --get core.hooksPath
if ($current -and $current -ne $hooksPosix) { Say "core.hooksPath was '$current'; replacing it." }
git config --global core.hooksPath $hooksPosix

Set-Content -Path (Join-Path $home_ ".last-refresh") -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -Encoding ascii

$config = Join-Path $repo "gate.config.yaml"
function Gate { if (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue) { & ai-sdlc-gate @args } else { & cmd /c "$py -m ai_sdlc_gate.cli $($args -join ' ')" } }

Say "Verifying"
Gate validate-skills --config $config

Say "Fetching the review configuration from the central repository (uses your GitHub sign-in)"
Gate configure --config $config
if ($LASTEXITCODE -ne 0) { Say "Could not fetch the configuration yet; run 'ai-sdlc-gate configure' after signing in to GitHub (gh auth login)." }

Gate identity check --config $config --strict 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Say "Signing you in with your Microsoft work account (one-time)"
  Gate identity login --config $config
}
Say "Done. Every commit and push on this machine now goes through the AI SDLC Gate."
