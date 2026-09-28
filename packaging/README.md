# Packaging — self-contained installers

Goal: a **double-click installer** that needs no system Python, no Git clone, and no access to the central
repository — so any colleague can install the gate and onboard with only their Microsoft sign-in.

## Windows (`windows/`)

| File | Role |
|---|---|
| `entry.py` | PyInstaller entry point → `ai_sdlc_gate.cli:main` |
| `ai-sdlc-gate.spec` | freezes the CLI into one `ai-sdlc-gate.exe` (bundled CPython) |
| `installer.iss` | Inno Setup: per-user install, lays policy under `%USERPROFILE%\.ai-sdlc-gate`, sets `core.hooksPath`, runs sign-in + `configure` |
| `build.ps1` | orchestrates: build venv → PyInstaller → stage policy → `iscc` |
| `../../.github/workflows/build-windows.yml` | CI: builds on `windows-latest`, uploads the installer, attaches it to a tagged release |

### What the installed layout looks like
```
%LOCALAPPDATA%\Programs\ai-sdlc-gate\ai-sdlc-gate.exe   (on PATH)
%USERPROFILE%\.ai-sdlc-gate\repo\gate.config.yaml       (policy)
%USERPROFILE%\.ai-sdlc-gate\repo\skills\...             (the 8 phase skills)
%USERPROFILE%\.ai-sdlc-gate\hooks\{commit-msg,pre-push,refresh-skills}
```
The existing hooks already look in exactly these paths and find the engine via `PATH`, so nothing about the
review flow changes — only the Python/venv/clone dependency is removed.

### Build locally
```powershell
pwsh packaging/windows/build.ps1 -Version 1.0.0
# -> dist\ai-sdlc-gate-setup-1.0.0.exe
```
Requires Python 3.10+ and Inno Setup 6 (`iscc` on PATH). CI does both on the runner.

### Not done here (needs your side)
- **Code signing.** Unsigned installers trip SmartScreen. Add an EV/OV cert and `signtool` in CI
  (sign both `ai-sdlc-gate.exe` and the setup `.exe`).
- **A verified build/test pass on a real Windows runner.** The PyInstaller hidden-imports (keyring's Windows
  backend, `win32ctypes`) are the usual failure point; confirm `ai-sdlc-gate configure` runs from the frozen exe.
- **Policy freshness.** This bundles a snapshot of `skills/` + `gate.config.yaml`; policy changes ship in the next
  installer release. If you want live policy updates instead, keep `refresh-skills` pulling from the repo (needs
  read access) — a deliberate trade-off vs. zero-repo-access.

## macOS / Linux
Not built yet. The same shape applies: PyInstaller one-file binary + a `.pkg` (macOS) / distro package or a
self-extracting script (Linux), laying the same `~/.ai-sdlc-gate` layout. Add when Windows is proven.
