#!/usr/bin/env bash
# AI SDLC Gate — remove the self-service client from this machine (Linux, macOS, WSL, Git Bash).
set -u
HOME_DIR="${AI_SDLC_GATE_HOME:-$HOME/.ai-sdlc-gate}"
CURRENT="$(git config --global --get core.hooksPath 2>/dev/null || true)"
case "$CURRENT" in *".ai-sdlc-gate/hooks"*) git config --global --unset core.hooksPath && echo "global git hooks path removed";; esac
if command -v ai-sdlc-gate >/dev/null 2>&1; then ai-sdlc-gate configure --clear >/dev/null 2>&1 && echo "gateway configuration removed from the credential store"; ai-sdlc-gate identity logout >/dev/null 2>&1 || true; fi
rm -rf "$HOME_DIR" && echo "removed $HOME_DIR"
for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -m pip uninstall -y -q ai-sdlc-gate >/dev/null 2>&1 && echo "removed the ai-sdlc-gate package ($c)"; done
command -v pipx >/dev/null 2>&1 && pipx uninstall ai-sdlc-gate >/dev/null 2>&1 && echo "removed the ai-sdlc-gate package (pipx)"
echo "AI SDLC Gate has been removed from this machine."
