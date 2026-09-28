# PyInstaller spec — builds a single-file ai-sdlc-gate.exe with a bundled CPython runtime,
# so target machines need no system Python.
#
# Build (from the repo root, in a venv that has `pip install ./gate pyinstaller`):
#     pyinstaller --clean --noconfirm packaging/windows/ai-sdlc-gate.spec
# Output: dist/ai-sdlc-gate.exe
#
# The engine reads its policy (skills/, gate.config.yaml) and git hooks from disk at runtime;
# the Windows installer lays those down under %USERPROFILE%\.ai-sdlc-gate, so they are NOT
# embedded in the binary. That keeps policy/skills updatable without re-releasing the exe.

from PyInstaller.utils.hooks import collect_submodules

# keyring picks its Windows backend dynamically; PyInstaller cannot see that by static analysis.
hiddenimports = (
    collect_submodules("keyring.backends")
    + collect_submodules("cryptography")
    + ["win32ctypes.core", "win32timezone"]
)

# The gate CLI is review/policy only; exclude the server-side and test stacks to keep the binary small.
excludes = ["fastapi", "starlette", "uvicorn", "pydantic", "pytest", "_pytest", "coverage", "tkinter"]

a = Analysis(
    ["entry.py"],
    pathex=["../../gate"],   # so `import ai_sdlc_gate` resolves to the source tree
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ai-sdlc-gate",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    # Sign in CI after the build:  signtool sign /fd SHA256 /tr <TSA> /td SHA256 dist/ai-sdlc-gate.exe
)
