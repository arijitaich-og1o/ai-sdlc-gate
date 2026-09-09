#!/usr/bin/env bash
# AI SDLC Gate installer for macOS. Double-click in Finder, or run from a terminal.
# Requires git (Xcode command line tools) and Python 3.10+ (https://www.python.org/downloads/macos/).
cd "$(dirname "$0")" || exit 1
if [ -f ./install.sh ]; then
  bash ./install.sh
else
  # Standalone download: fetch the repository with git (uses your GitHub sign-in) and run the installer from it.
  [ -d "$HOME/.ai-sdlc-gate/repo/.git" ] || git clone --depth 1 https://github.com/arijitaich-og1o/ai-sdlc-gate "$HOME/.ai-sdlc-gate/repo"
  bash "$HOME/.ai-sdlc-gate/repo/client/install.sh"
fi
STATUS=$?
echo
if [ "$STATUS" = 0 ]; then
  echo "[ai-sdlc-gate] Installed. Restart your terminals and IDEs."
else
  echo "[ai-sdlc-gate] Installation did not complete. See the messages above."
fi
read -r -p "Press Enter to close this window."
exit $STATUS
