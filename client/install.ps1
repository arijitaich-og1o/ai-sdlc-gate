<#
.SYNOPSIS
  SDLC Gate developer installer for Windows (PowerShell 5.1+ / 7+, with Git for Windows).

.DESCRIPTION
  1. clones (or refreshes) the central repository to %USERPROFILE%\.sdlc-gate\repo
  2. installs the `sdlc-gate` CLI for the current user (pipx if available, else pip --user)
  3. installs global git hooks (commit-msg, pre-push) via core.hooksPath. Git for Windows runs hooks with its
     bundled sh, so the same bash hooks work in PowerShell, cmd, VS Code, IntelliJ and any other IDE.
  4. stores the LiteLLM endpoint + key in %USERPROFILE%\.sdlc-gate\env (user-only ACL)

.EXAMPLE
  irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = $(if ($env:SDLC_GATE_REPO_URL) { $env:SDLC_GATE_REPO_URL } else { "https://github.com/arijitaich-og1o/ai-sdlc-gate.git" }),
  [string]$Ref = $(if ($env:SDLC_GATE_REF) { $env:SDLC_GATE_REF } else { "main" }),
  [string]$BaseUrl = $(if ($env:LITELLM_BASE_URL) { $env:LITELLM_BASE_URL } else { "https://litellm-dev.dev.aime.osp-fine.de" }),
  [string]$ApiKey = $env:LITELLM_API_KEY
)

$ErrorActionPreference = "Stop"
function Say($m) { Write-Host "[sdlc-gate] $m" -ForegroundColor Cyan }
function Die($m) { Write-Host "[sdlc-gate] $m" -ForegroundColor Red; exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git is required (Git for Windows)" }
$py = $null
foreach ($c in @("py -3", "python", "python3")) {
  try {
    $v = & cmd /c "$c -c ""import sys; print(sys.version_info >= (3,10))""" 2>$null
    if ($v -match "True") { $py = $c; break }
  } catch {}
}
if (-not $py) { Die "Python 3.10+ is required" }

$home_ = if ($env:SDLC_GATE_HOME) { $env:SDLC_GATE_HOME } else { Join-Path $env:USERPROFILE ".sdlc-gate" }
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

Say "Installing the sdlc-gate CLI"
if (Get-Command pipx -ErrorAction SilentlyContinue) {
  pipx install --force --quiet (Join-Path $repo "gate") | Out-Null
} else {
  & cmd /c "$py -m pip install --quiet --user --upgrade ""$(Join-Path $repo 'gate')"""
  $scripts = & cmd /c "$py -c ""import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"""
  if ($scripts -and -not (Get-Command sdlc-gate -ErrorAction SilentlyContinue)) {
    Say "Adding $scripts to the user PATH (restart your terminal/IDE afterwards)"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$scripts*") { [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User") }
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

$envFile = Join-Path $home_ "env"
if (-not (Test-Path $envFile) -or $ApiKey) {
  if (-not $ApiKey) {
    $secure = Read-Host -AsSecureString "LiteLLM API key (stored in $envFile)"
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($secure))
  }
  if ($ApiKey) {
    $content = "export LITELLM_BASE_URL='$BaseUrl'`nexport LITELLM_API_KEY='$ApiKey'`n"
    [IO.File]::WriteAllText($envFile, $content)
    # Restrict the file to the current user.
    icacls $envFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Say "Stored LiteLLM configuration in $envFile"
  } else {
    Say "No LiteLLM key provided; local hooks will skip the model review until $envFile exists."
  }
}
Set-Content -Path (Join-Path $home_ ".last-refresh") -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -Encoding ascii

Say "Verifying"
if (Get-Command sdlc-gate -ErrorAction SilentlyContinue) {
  sdlc-gate validate-skills --config (Join-Path $repo "gate.config.yaml")
  sdlc-gate identity show --quiet --config (Join-Path $repo "gate.config.yaml") 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Say "Signing you in with your Microsoft work account (one-time)"
    sdlc-gate identity login --config (Join-Path $repo "gate.config.yaml")
  }
}
Say "Done. Every commit and push on this machine now runs the SDLC Gate locally; GitHub enforces it centrally."
