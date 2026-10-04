"""PyInstaller entry point for the bundled macOS `ai-sdlc-gate` binary.

Delegates to the installed console-script entry (`ai_sdlc_gate.cli:main`) so the frozen binary behaves
exactly like `ai-sdlc-gate`.
"""
import sys

from ai_sdlc_gate.cli import main

if __name__ == "__main__":
    sys.exit(main())
