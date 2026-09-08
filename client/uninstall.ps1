<#
.SYNOPSIS
  AI SDLC Gate — remove the self-service client from this machine (Windows).
#>
$ErrorActionPreference = "Continue"
$home_ = if ($env:AI_SDLC_GATE_HOME) { $env:AI_SDLC_GATE_HOME } else { Join-Path $env:USERPROFILE ".ai-sdlc-gate" }
$current = git config --global --get core.hooksPath
if ($current -like "*.ai-sdlc-gate/hooks*") { git config --global --unset core.hooksPath; Write-Host "global git hooks path removed" }
if (Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue) {
  ai-sdlc-gate configure --clear 2>$null | Out-Null; Write-Host "gateway configuration removed from Windows Credential Manager"
  ai-sdlc-gate identity logout 2>$null | Out-Null
}
if (Test-Path $home_) { Remove-Item -Recurse -Force $home_; Write-Host "removed $home_" }
foreach ($c in @("py -3", "python")) { try { & cmd /c "$c -m pip uninstall -y -q ai-sdlc-gate" 2>$null | Out-Null; Write-Host "removed the ai-sdlc-gate package ($c)" } catch {} }
if (Get-Command pipx -ErrorAction SilentlyContinue) { pipx uninstall ai-sdlc-gate 2>$null | Out-Null }
Write-Host "AI SDLC Gate has been removed from this machine."
