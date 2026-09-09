#!/usr/bin/env bash
# AI SDLC Gate — remove the self-service client from this machine (Linux, macOS, WSL, Git Bash).
set -u
HOME_DIR="${AI_SDLC_GATE_HOME:-$HOME/.ai-sdlc-gate}"
CURRENT="$(git config --global --get core.hooksPath 2>/dev/null || true)"
case "$CURRENT" in *".ai-sdlc-gate/hooks"*) git config --global --unset core.hooksPath && echo "global git hooks path removed";; esac
CLI=""
if command -v ai-sdlc-gate >/dev/null 2>&1; then CLI="ai-sdlc-gate"; else
  for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -m ai_sdlc_gate.cli --version >/dev/null 2>&1 && { CLI="$c -m ai_sdlc_gate.cli"; break; }; done
fi
if [ -n "$CLI" ]; then
  $CLI configure --clear >/dev/null 2>&1 && echo "gateway configuration removed from the credential store"
  $CLI identity logout >/dev/null 2>&1 || true
else
  for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "import keyring; keyring.delete_password('ai-sdlc-gate','gateway-config')" >/dev/null 2>&1 && { echo "gateway configuration removed from the credential store"; break; }; done
fi
for prof in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.zshenv"; do [ -f "$prof" ] && grep -q "# ai-sdlc-gate" "$prof" && sed -i.bak '/# ai-sdlc-gate$/d' "$prof" && rm -f "$prof.bak"; done
rm -rf "$HOME_DIR" && echo "removed $HOME_DIR"
for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -m pip uninstall -y -q ai-sdlc-gate >/dev/null 2>&1 && echo "removed the ai-sdlc-gate package ($c)"; done
command -v pipx >/dev/null 2>&1 && pipx uninstall ai-sdlc-gate >/dev/null 2>&1 && echo "removed the ai-sdlc-gate package (pipx)"
echo "AI SDLC Gate has been removed from this machine."
