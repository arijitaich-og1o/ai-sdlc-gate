<#
.SYNOPSIS
  AI SDLC Gate developer installer for Windows (PowerShell 5.1+ / 7+, with Git for Windows).

.DESCRIPTION
  1. clones (or refreshes) the central repository to %USERPROFILE%\.ai-sdlc-gate\repo
  2. installs the `ai-sdlc-gate` CLI into a private virtual environment (%USERPROFILE%\.ai-sdlc-gate\venv)
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
# Abort rather than hang if the network stalls: fail a transfer that stays under 1 KB/s for 60s.
$gitTimeout = @("-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=60")
if (Test-Path (Join-Path $repo ".git")) {
  git @gitTimeout -C $repo fetch --quiet --depth 1 origin $Ref
  git -C $repo reset --quiet --hard FETCH_HEAD
} else {
  if (Test-Path $repo) { Remove-Item -Recurse -Force $repo }
  git @gitTimeout clone --quiet --depth 1 --branch $Ref $RepoUrl $repo
}
Set-Content -Path (Join-Path $home_ "ref") -Value $Ref -Encoding ascii

Say "Installing the ai-sdlc-gate CLI (private Python environment)"
Remove-Item -Recurse -Force (Join-Path $repo "gate\build"), (Join-Path $repo "gate\*.egg-info") -ErrorAction SilentlyContinue
$venv = Join-Path $home_ "venv"
$vpy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $vpy)) { & cmd /c "$py -m venv ""$venv"""; if (-not (Test-Path $vpy)) { throw "Could not create a Python virtual environment in $venv" } }
& $vpy -m pip install --quiet --upgrade pip setuptools wheel 2>&1 | Out-Null
& $vpy -m pip install --quiet --upgrade (Join-Path $repo "gate")
if ($LASTEXITCODE -ne 0) { throw "Could not install the engine into $venv" }
$vbin = Join-Path $venv "Scripts"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$vbin*") { [Environment]::SetEnvironmentVariable("Path", "$vbin;$userPath", "User"); Say "Added $vbin to your PATH so 'ai-sdlc-gate' works by name (restart terminals/IDEs)." }
$env:Path = "$vbin;$env:Path"

$config = Join-Path $repo "gate.config.yaml"
# Native programs that write to stderr make PowerShell 5.1 throw under $ErrorActionPreference = "Stop".
# Run the CLI through cmd with stderr merged so all output is plain text; the exit code stays in $LASTEXITCODE.
function GateCmd { "$vbin\ai-sdlc-gate.exe" }
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
# We do NOT set a persistent GIT_CONFIG_PARAMETERS override. That environment variable outranks the git config file
# and lingers in already-open shells, so a value left by an earlier install can point git at a removed hooks path
# and break commits until every terminal is restarted - a confusing failure. The global core.hooksPath above is
# read fresh on every git call and takes effect immediately. Actively clear any stale override left by an older
# install so this machine self-heals. (Repositories that set their own core.hooksPath - husky and friends - are
# handled by the managed install's git shim and by the server-side branch-protection ruleset.)
# Match the exact shape we ever wrote (core.hooksPath pointing at the ai-sdlc-gate hooks) so an unrelated value a
# developer set for their own reasons is never touched. -like is case-insensitive.
if (([Environment]::GetEnvironmentVariable("GIT_CONFIG_PARAMETERS", "User")) -like "*core.hooksPath=*ai-sdlc-gate*") {
  [Environment]::SetEnvironmentVariable("GIT_CONFIG_PARAMETERS", $null, "User")
  Say "Removed a stale GIT_CONFIG_PARAMETERS from an earlier install; restart open terminals to clear it there too."
}
if ($env:GIT_CONFIG_PARAMETERS -like "*core.hooksPath=*ai-sdlc-gate*") { Remove-Item Env:\GIT_CONFIG_PARAMETERS -ErrorAction SilentlyContinue }

Say "Step 3 of 3: preparing the review engine (uses your GitHub sign-in)"
Gate configure --config $config
if ($LASTEXITCODE -ne 0) { Say "The review engine could not be prepared yet; run 'ai-sdlc-gate configure' after signing in to GitHub (gh auth login)." }

Say "Verifying"
Gate validate-skills --config $config | Select-Object -Last 1

Set-Content -Path (Join-Path $home_ ".last-refresh") -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -Encoding ascii

# WSL is a separate Linux system with its own git and Python. This Windows installer does not reach into WSL: to
# gate commits made from inside a WSL distribution, open that distribution and run client/install.sh there.
if ((Get-Command wsl.exe -ErrorAction SilentlyContinue) -and $env:AI_SDLC_GATE_WSL -eq "1") {
  Say "WSL: to install the gate inside a WSL distribution, open it and run: bash ~/.ai-sdlc-gate/repo/client/install.sh"
}

Say "Done. Every commit and push on this machine now goes through the AI SDLC Gate."
