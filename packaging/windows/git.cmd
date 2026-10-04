@echo off
rem AI SDLC Gate git shim (Windows, visibility mode).
rem A bypass (git ... --no-verify) is ALLOWED but reported to the organisation endpoint, so the skip is tracked
rem live. It changes NO arguments and only observes; on ANY problem it still runs the real git, so it can never
rem break git for the developer. Installed next to ai-sdlc-gate.exe, on the machine PATH ahead of Git for Windows.

rem Resolve the real git.exe (this shim is a .cmd, so `where git.exe` never finds the shim itself).
set "_AISDLC_REALGIT="
for /f "delims=" %%G in ('where git.exe 2^>nul') do if not defined _AISDLC_REALGIT set "_AISDLC_REALGIT=%%G"
if not defined _AISDLC_REALGIT set "_AISDLC_REALGIT=git.exe"

rem Read-only scan for --no-verify (shift does not affect %*, which is passed through verbatim below).
set "_AISDLC_BYPASS="
:aisdlc_scan
if "%~1"=="" goto aisdlc_done
if /I "%~1"=="--no-verify" set "_AISDLC_BYPASS=1"
shift
goto aisdlc_scan
:aisdlc_done
if defined _AISDLC_BYPASS start "" /b ai-sdlc-gate report-skip --config "%USERPROFILE%\.ai-sdlc-gate\repo\gate.config.yaml" --command "no-verify" >nul 2>&1

"%_AISDLC_REALGIT%" %*
exit /b %ERRORLEVEL%
