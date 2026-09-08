#!/usr/bin/env bash
# AI SDLC Gate developer installer (Linux, macOS, WSL, Git Bash).
#
#   curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash
#
# What it does
#   1. clones (or refreshes) the central repository to ~/.ai-sdlc-gate/repo
#   2. installs the `ai-sdlc-gate` CLI for the current user (pipx if available, else pip --user)
#   3. installs global git hooks (commit-msg, pre-push) via core.hooksPath, chaining to repo-local hooks
#   4. obtains the review configuration from the central repository (key broker) and keeps it in the OS credential
#      store (macOS Keychain / Linux Secret Service; encrypted file fallback on headless machines)
#   5. signs the developer in with their Microsoft work account (one-time)
#
# Environment overrides: AI_SDLC_GATE_REPO_URL, AI_SDLC_GATE_REF, AI_SDLC_GATE_HOME
set -euo pipefail

REPO_URL="${AI_SDLC_GATE_REPO_URL:-https://github.com/arijitaich-og1o/ai-sdlc-gate.git}"
REF="${AI_SDLC_GATE_REF:-main}"
SDLC_HOME="${AI_SDLC_GATE_HOME:-$HOME/.ai-sdlc-gate}"

say() { printf '\033[1;34m[ai-sdlc-gate]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[ai-sdlc-gate] %s\033[0m\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.10+ is required"

mkdir -p "$SDLC_HOME/hooks"
chmod 700 "$SDLC_HOME"

say "Syncing central repository ($REF) to $SDLC_HOME/repo"
if [ -d "$SDLC_HOME/repo/.git" ]; then
  git -C "$SDLC_HOME/repo" fetch --quiet --depth 1 origin "$REF"
  git -C "$SDLC_HOME/repo" reset --quiet --hard FETCH_HEAD
else
  rm -rf "$SDLC_HOME/repo"
  git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$SDLC_HOME/repo"
fi
printf '%s\n' "$REF" > "$SDLC_HOME/ref"

say "Installing the ai-sdlc-gate CLI"
if command -v pipx >/dev/null 2>&1; then
  pipx install --force --quiet "$SDLC_HOME/repo/gate" >/dev/null
else
  "$PY" -m pip install --quiet --user --upgrade "$SDLC_HOME/repo/gate"
  USER_BIN="$("$PY" -c 'import sysconfig; print(sysconfig.get_path("scripts", "posix_user" if __import__("os").name != "nt" else "nt_user"))' 2>/dev/null || true)"
  if [ -n "$USER_BIN" ] && ! command -v ai-sdlc-gate >/dev/null 2>&1; then
    say "Add $USER_BIN to your PATH so git hooks can find ai-sdlc-gate"
  fi
fi

say "Installing global git hooks"
for h in commit-msg pre-push refresh-skills; do
  install -m 755 "$SDLC_HOME/repo/client/hooks/$h" "$SDLC_HOME/hooks/$h"
done
CURRENT_HOOKS="$(git config --global --get core.hooksPath || true)"
if [ -n "$CURRENT_HOOKS" ] && [ "$CURRENT_HOOKS" != "$SDLC_HOME/hooks" ]; then
  say "core.hooksPath is currently '$CURRENT_HOOKS'. It will be replaced; hooks in that directory will no longer run."
fi
git config --global core.hooksPath "$SDLC_HOME/hooks"

date +%s > "$SDLC_HOME/.last-refresh"

GATE="ai-sdlc-gate"
command -v ai-sdlc-gate >/dev/null 2>&1 || GATE="$PY -m ai_sdlc_gate.cli"
CONFIG="$SDLC_HOME/repo/gate.config.yaml"

say "Verifying"
$GATE validate-skills --config "$CONFIG"

say "Fetching the review configuration from the central repository (uses your GitHub sign-in)"
$GATE configure --config "$CONFIG" || say "Could not fetch the configuration yet; run 'ai-sdlc-gate configure' after signing in to GitHub (gh auth login)."

if [ -t 0 ] && ! $GATE identity check --config "$CONFIG" --strict >/dev/null 2>&1; then
  say "Signing you in with your Microsoft work account (one-time)"
  $GATE identity login --config "$CONFIG" || say "Identity sign-in skipped; run 'ai-sdlc-gate identity login' later."
fi
say "Done. Every commit and push on this machine now goes through the AI SDLC Gate."
