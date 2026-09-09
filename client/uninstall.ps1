<#
.SYNOPSIS
  AI SDLC Gate — remove the self-service client from this machine (Windows).
#>
$ErrorActionPreference = "Continue"
$home_ = if ($env:AI_SDLC_GATE_HOME) { $env:AI_SDLC_GATE_HOME } else { Join-Path $env:USERPROFILE ".ai-sdlc-gate" }
$current = git config --global --get core.hooksPath
if ($current -like "*.ai-sdlc-gate/hooks*") { git config --global --unset core.hooksPath; Write-Host "global git hooks path removed" }
if (([Environment]::GetEnvironmentVariable("GIT_CONFIG_PARAMETERS", "User")) -like "*ai-sdlc-gate*") { [Environment]::SetEnvironmentVariable("GIT_CONFIG_PARAMETERS", $null, "User"); Write-Host "git environment override removed" }
$cli = if (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue) { "ai-sdlc-gate" } else { $null }
if (-not $cli) { foreach ($c in @("py -3", "python")) { & cmd /c "$c -m ai_sdlc_gate.cli --version >nul 2>&1"; if ($LASTEXITCODE -eq 0) { $cli = "$c -m ai_sdlc_gate.cli"; break } } }
if ($cli) {
  & cmd /c "$cli configure --clear >nul 2>&1"; Write-Host "gateway configuration removed from Windows Credential Manager"
  & cmd /c "$cli identity logout >nul 2>&1"
} else {
  # Last resort: clear the entry directly.
  foreach ($c in @("py -3", "python")) { & cmd /c "$c -c ""import keyring; keyring.delete_password('ai-sdlc-gate','gateway-config')"" >nul 2>&1"; if ($LASTEXITCODE -eq 0) { Write-Host "gateway configuration removed from Windows Credential Manager"; break } }
}
if (Test-Path $home_) { Remove-Item -Recurse -Force $home_; Write-Host "removed $home_" }
foreach ($c in @("py -3", "python")) { try { & cmd /c "$c -m pip uninstall -y -q ai-sdlc-gate" 2>$null | Out-Null; Write-Host "removed the ai-sdlc-gate package ($c)" } catch {} }
if (Get-Command pipx -ErrorAction SilentlyContinue) { pipx uninstall ai-sdlc-gate 2>$null | Out-Null }
Write-Host "AI SDLC Gate has been removed from this machine."
