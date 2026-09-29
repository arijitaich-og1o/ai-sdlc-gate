# PyInstaller spec — builds a single-file macOS `ai-sdlc-gate` binary with a bundled CPython runtime.
# Built on a macOS runner (see .github/workflows/build-macos.yml); cannot be produced on Windows/Linux.
#
#     pyinstaller --clean --noconfirm packaging/macos/ai-sdlc-gate-mac.spec   # -> dist/ai-sdlc-gate
#
# Policy (skills, gate.config.yaml) and git hooks are laid down by the installer's postinstall, not embedded here.

from PyInstaller.utils.hooks import collect_submodules

# keyring resolves its macOS Keychain backend dynamically; PyInstaller cannot see that statically.
hiddenimports = collect_submodules("keyring.backends") + collect_submodules("cryptography")

excludes = ["fastapi", "starlette", "uvicorn", "pydantic", "pytest", "_pytest", "coverage", "tkinter",
            "win32ctypes", "win32timezone"]

a = Analysis(
    ["entry.py"],
    pathex=["../../gate"],
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
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="ai-sdlc-gate",
    debug=False, strip=False, upx=False, console=True,
)
