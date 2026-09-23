@echo off
rem AI SDLC Gate installer for Windows. Double-click, or run from a terminal.
rem Requires Git for Windows and Python 3.10+ (https://www.python.org/downloads/windows/).
setlocal
set "HERE=%~dp0"
rem A bundled deployment ships the review configuration as gate.record next to this file: the installer imports it
rem and never contacts the key broker, so a tester needs no GitHub permission.
if exist "%HERE%gate.record" set "AI_SDLC_GATE_RECORD_FILE=%HERE%gate.record"
if exist "%HERE%install.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%install.ps1"
) else (
  rem Standalone download: fetch the public repository with git and run the installer from it.
  if not exist "%USERPROFILE%\.ai-sdlc-gate\repo\.git" git clone --depth 1 https://github.com/arijitaich-og1o/ai-sdlc-gate "%USERPROFILE%\.ai-sdlc-gate\repo"
  powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.ai-sdlc-gate\repo\client\install.ps1"
)
if errorlevel 1 (
  echo.
  echo [ai-sdlc-gate] Installation did not complete. See the messages above.
) else (
  echo.
  echo [ai-sdlc-gate] Installed. Restart your terminals and IDEs so they pick up the new PATH.
)
pause
