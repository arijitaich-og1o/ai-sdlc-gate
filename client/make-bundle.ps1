<#
.SYNOPSIS
  Build a self-contained "does everything" tester installer for the AI SDLC Gate (Windows/macOS).

.DESCRIPTION
  Run this ONCE on a machine that is already configured (has the review configuration). It exports the
  configuration as `gate.record` and packages it with the double-click launchers into a zip a tester can run with
  no GitHub permission and no key-broker call:

    ai-sdlc-gate-installer/
      install.cmd       (Windows: double-click)
      install.command   (macOS: double-click)
      gate.record       (the review configuration, imported by the installer)
      README.txt

  SECURITY: gate.record contains the model credential (a least-privilege, spend-capped service account). Send the
  zip only to trusted testers over a secure channel, never commit it, and rotate the credential after the trial.
#>
[CmdletBinding()]
param(
  [string]$OutDir = (Join-Path $PSScriptRoot "..\dist"),
  [string]$Gate = ""
)
$ErrorActionPreference = "Stop"

if (-not $Gate) { $c = Get-Command ai-sdlc-gate -ErrorAction SilentlyContinue; if ($c) { $Gate = $c.Source } }
if (-not $Gate -or -not (Test-Path $Gate)) { $Gate = Join-Path $env:USERPROFILE ".ai-sdlc-gate\venv\Scripts\ai-sdlc-gate.exe" }
if (-not (Test-Path $Gate)) { throw "ai-sdlc-gate CLI not found. Install and 'ai-sdlc-gate configure' on this machine first." }

$stage = Join-Path $OutDir "ai-sdlc-gate-installer"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# Export the review configuration (contains the model credential). Written owner-readable inside the staging dir.
& cmd /c "`"$Gate`" configure --export-record > `"$stage\gate.record`" 2>nul"
if (-not (Test-Path "$stage\gate.record") -or (Get-Item "$stage\gate.record").Length -lt 10) {
  throw "Could not export the review configuration. Run 'ai-sdlc-gate configure' on this machine, then retry."
}

Copy-Item (Join-Path $PSScriptRoot "install.cmd") $stage
Copy-Item (Join-Path $PSScriptRoot "install.command") $stage
Copy-Item (Join-Path $PSScriptRoot "bootstrap.ps1") $stage
@"
AI SDLC Gate - one-step tester install
======================================
1. Unzip this folder anywhere.
2. Windows: double-click  install.cmd
   macOS:   double-click  install.command   (first time: right-click -> Open)
3. If Windows shows a blue "Windows protected your PC" box: More info -> Run anyway.
4. When the browser opens, sign in with your @og1o.in work account. Nothing to type.

That's all. On Windows, if Python or Git are missing they are installed for you
automatically (no administrator rights needed) - you just need an internet connection.
The gate then reviews every commit and push on this machine.

Note: gate.record in this folder holds the review configuration - keep it private, do not re-share.
"@ | Set-Content (Join-Path $stage "README.txt") -Encoding ascii

$zip = Join-Path $OutDir "ai-sdlc-gate-installer.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip
Write-Host "[ai-sdlc-gate] Bundle ready: $zip"
Write-Host "[ai-sdlc-gate] SECURITY: gate.record carries the model credential. Send only to trusted testers over a secure channel; never commit it; rotate the credential after the trial."
