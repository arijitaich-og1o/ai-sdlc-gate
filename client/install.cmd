@echo off
rem AI SDLC Gate installer for Windows. Double-click, or run from a terminal.
rem Requires Git for Windows and Python 3.10+ (https://www.python.org/downloads/windows/).
setlocal
set "HERE=%~dp0"
rem A bundled deployment ships the review configuration as gate.record next to this file: the installer imports it
rem and never contacts the key broker, so a tester needs no GitHub permission.
if exist "%HERE%gate.record" set "AI_SDLC_GATE_RECORD_FILE=%HERE%gate.record"
if exist "%HERE%bootstrap.ps1" (
  rem Zero-prerequisite bundle: bootstrap installs Python and Git for the current user if missing, then installs.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%bootstrap.ps1"
) else if exist "%HERE%install.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%install.ps1"
) else (
  rem Standalone download: bootstrap dependencies and install from the public repository.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$b='%USERPROFILE%\.ai-sdlc-gate\repo\client\bootstrap.ps1'; if(-not(Test-Path $b)){ $t=Join-Path $env:TEMP 'ai-sdlc-bootstrap.ps1'; Invoke-WebRequest 'https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/bootstrap.ps1' -OutFile $t; $b=$t }; & $b"
)
if errorlevel 1 (
  echo.
  echo [ai-sdlc-gate] Installation did not complete. See the messages above.
) else (
  echo.
  echo [ai-sdlc-gate] Installed. Restart your terminals and IDEs so they pick up the new PATH.
)
pause
