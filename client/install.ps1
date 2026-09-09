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
  git clone https://github.com/arijitaich-og1o/ai-sdlc-gate "$env:USERPROFILE\.ai-sdlc-gate\repo"; & "$env:USERPROFILE\.ai-sdlc-gate\repo\client\install.ps1"
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

$config = Join-Path $repo "gate.config.yaml"
# Native programs that write to stderr make PowerShell 5.1 throw under $ErrorActionPreference = "Stop".
# Run the CLI through cmd with stderr merged so all output is plain text; the exit code stays in $LASTEXITCODE.
function GateCmd { if (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue) { "ai-sdlc-gate" } else { "$py -m ai_sdlc_gate.cli" } }
function Gate { $q = ($args | ForEach-Object { '"' + $_ + '"' }) -join ' '; & cmd /c "$(GateCmd) $q 2>&1" }
function GateQuiet { $q = ($args | ForEach-Object { '"' + $_ + '"' }) -join ' '; & cmd /c "$(GateCmd) $q >nul 2>&1" }

# Step 1: who you are. Runs first so the developer sees the code immediately.
GateQuiet identity check --config $config --strict
if ($LASTEXITCODE -ne 0 -and $env:AI_SDLC_GATE_NONINTERACTIVE -ne "1") {
  Say "Step 1 of 3: sign in with your Microsoft work account"
  Gate identity login --config $config
  if ($LASTEXITCODE -ne 0) { Say "Sign-in not completed; run 'ai-sdlc-gate identity login' later." }
} elseif ($LASTEXITCODE -eq 0) {
  Say "Step 1 of 3: already signed in"
} else {
  Say "Step 1 of 3: sign-in skipped; run 'ai-sdlc-gate identity login' later."
}

Say "Step 2 of 3: installing the git hooks"
foreach ($h in @("commit-msg", "pre-push", "refresh-skills")) {
  Copy-Item -Force (Join-Path $repo "client\hooks\$h") (Join-Path $hooks $h)
}
$hooksPosix = $hooks -replace "\\", "/"
$current = git config --global --get core.hooksPath
if ($current -and $current -ne $hooksPosix) { Say "core.hooksPath was '$current'; replacing it (the gate chains to repository hooks itself)." }
git config --global core.hooksPath $hooksPosix
# Repositories may set their own core.hooksPath (husky and friends). Git's environment override wins over repository
# configuration, so set it for the user; IDEs and GUI clients started afterwards inherit it.
$gitParams = "'core.hooksPath=$hooksPosix'"
[Environment]::SetEnvironmentVariable("GIT_CONFIG_PARAMETERS", $gitParams, "User")
$env:GIT_CONFIG_PARAMETERS = $gitParams

Say "Step 3 of 3: preparing the review engine (uses your GitHub sign-in)"
Gate configure --config $config
if ($LASTEXITCODE -ne 0) { Say "The review engine could not be prepared yet; run 'ai-sdlc-gate configure' after signing in to GitHub (gh auth login)." }

Say "Verifying"
Gate validate-skills --config $config | Select-Object -Last 1

Set-Content -Path (Join-Path $home_ ".last-refresh") -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -Encoding ascii

# WSL is a separate Linux system with its own git. Install the gate in every distribution from the Windows copy of
# the repository (no network or GitHub credential needed inside WSL) and carry the sign-in and review engine over.
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
  $distros = @()
  try { $distros = (& wsl.exe -l -q 2>$null) -replace "\x00", "" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch "docker-desktop" } } catch {}
  if ($distros.Count -gt 0) {
    $drive = $home_.Substring(0, 1).ToLower()
    $winHomeWsl = "/mnt/$drive" + ($home_.Substring(2) -replace "\\", "/")
    $record = Join-Path $home_ "handover.json"
    & cmd /c "$(GateCmd) configure --export-record > ""$record"" 2>nul"
    foreach ($d in $distros) {
      Say "WSL: installing the gate in '$d'"
      $cmd = "export AI_SDLC_GATE_NONINTERACTIVE=1 AI_SDLC_GATE_REPO_URL='$winHomeWsl/repo' AI_SDLC_GATE_RECORD_FILE='$winHomeWsl/handover.json'; " +
             "bash '$winHomeWsl/repo/client/install.sh'; mkdir -p ~/.ai-sdlc-gate; " +
             "[ -f '$winHomeWsl/identity.json' ] && cp '$winHomeWsl/identity.json' ~/.ai-sdlc-gate/ && chmod 600 ~/.ai-sdlc-gate/identity.json; true"
      & cmd /c "wsl.exe -d $d -- bash -lc ""$cmd"" 2>&1" | Where-Object { $_ -notmatch "notice|pip is available|To update, run|WARNING: The script" }
      if ($LASTEXITCODE -ne 0) { Say "WSL '$d': the gate could not be installed there (git and Python 3.10+ are required inside WSL). Run 'bash $winHomeWsl/repo/client/install.sh' inside it later." }
    }
    if (Test-Path $record) { Remove-Item -Force $record }
  }
}

Say "Done. Every commit and push on this machine now goes through the AI SDLC Gate."
