@echo off
rem SDLC Gate installer for Windows. Double-click, or run from a terminal.
rem Requires Git for Windows and Python 3.10+ (https://www.python.org/downloads/windows/).
setlocal
set "HERE=%~dp0"
if exist "%HERE%install.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%install.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex"
)
if errorlevel 1 (
  echo.
  echo [sdlc-gate] Installation did not complete. See the messages above.
) else (
  echo.
  echo [sdlc-gate] Installed. Restart your terminals and IDEs so they pick up the new PATH.
)
pause
