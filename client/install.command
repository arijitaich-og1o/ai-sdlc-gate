#!/usr/bin/env bash
# AI SDLC Gate installer for macOS. Double-click in Finder, or run from a terminal.
# Requires git (Xcode command line tools) and Python 3.10+ (https://www.python.org/downloads/macos/).
cd "$(dirname "$0")" || exit 1
if [ -f ./install.sh ]; then
  bash ./install.sh
else
  curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash
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
