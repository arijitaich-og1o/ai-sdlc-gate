#!/usr/bin/env bash
# AI SDLC Gate developer installer (Linux, macOS, WSL, Git Bash).
#
#   git clone https://github.com/arijitaich-og1o/ai-sdlc-gate ~/.ai-sdlc-gate/repo && bash ~/.ai-sdlc-gate/repo/client/install.sh
#
# What it does
#   1. clones (or refreshes) the central repository to ~/.ai-sdlc-gate/repo
#   2. installs the `ai-sdlc-gate` CLI into a private virtual environment (~/.ai-sdlc-gate/venv)
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

# Reject values that could inject git options or shell metacharacters (leading '-', control chars, etc.).
if printf '%s' "$REF" | grep -Eq '^-|[[:cntrl:];|&$`<>()]'; then
  die "Invalid AI_SDLC_GATE_REF: refuse potentially unsafe ref"
fi
if printf '%s' "$REPO_URL" | grep -Eq '^-|[[:cntrl:];|&$`<>()]'; then
  die "Invalid AI_SDLC_GATE_REPO_URL: refuse potentially unsafe URL"
fi

command -v git >/dev/null 2>&1 || die "git is required"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.10+ is required"

mkdir -p "$SDLC_HOME/hooks"
chmod 700 "$SDLC_HOME"

say "Syncing central repository ($REF) to $SDLC_HOME/repo"
# The repository is private: cloning uses the developer's existing GitHub sign-in (credential helper). Inside WSL the
# Windows installer passes the already-synced Windows copy as REPO_URL, so no credential is needed there.
if [ -d "$SDLC_HOME/repo/.git" ]; then
  case "$REPO_URL" in /*) REPO_URL="file://$REPO_URL";; esac   # local path (WSL from the Windows copy): file:// keeps shallow fetches working
  git -C "$SDLC_HOME/repo" remote set-url origin "$REPO_URL" 2>/dev/null || true
  git -C "$SDLC_HOME/repo" fetch --quiet --depth 1 origin -- "$REF"
  git -C "$SDLC_HOME/repo" reset --quiet --hard FETCH_HEAD
else
  rm -rf "$SDLC_HOME/repo"
  case "$REPO_URL" in /*) REPO_URL="file://$REPO_URL";; esac
  git clone --quiet --depth 1 --branch "$REF" -- "$REPO_URL" "$SDLC_HOME/repo" || die "Could not clone the AI SDLC Gate repository. Sign in to GitHub in your browser once (a credential prompt should have appeared) and run the installer again."
fi
printf '%s\n' "$REF" > "$SDLC_HOME/ref"

say "Installing the ai-sdlc-gate CLI (private Python environment)"
rm -rf "$SDLC_HOME/repo/gate/build" "$SDLC_HOME/repo/gate"/*.egg-info 2>/dev/null || true
VENV="$SDLC_HOME/venv"
if [ ! -x "$VENV/bin/python" ] && [ ! -x "$VENV/Scripts/python.exe" ]; then
  "$PY" -m venv "$VENV" 2>/dev/null || { rm -rf "$VENV"; "$PY" -m venv --without-pip "$VENV" 2>/dev/null && "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1; } \
    || die "Could not create a Python virtual environment. On Debian/Ubuntu run: sudo apt install python3-venv  and try again."
fi
VPY="$VENV/bin/python"; [ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"
"$VPY" -m pip install --quiet --upgrade pip setuptools wheel >/dev/null 2>&1 || true
"$VPY" -m pip install --quiet --upgrade "$SDLC_HOME/repo/gate" || die "Could not install the engine into $VENV"
VBIN="$(dirname "$VPY")"
GATE="$VBIN/ai-sdlc-gate"; [ -x "$GATE" ] || GATE="$VBIN/ai-sdlc-gate.exe"
mkdir -p "$HOME/.local/bin" && ln -sf "$GATE" "$HOME/.local/bin/ai-sdlc-gate" 2>/dev/null || true
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) say "Add \$HOME/.local/bin to your PATH to run 'ai-sdlc-gate' by name (the hooks do not need it).";; esac

CONFIG="$SDLC_HOME/repo/gate.config.yaml"

# Step 1: who you are. Runs first so the developer sees the code immediately; skipped only when there is no
# terminal (automation) or AI_SDLC_GATE_NONINTERACTIVE=1.
if [ "${AI_SDLC_GATE_NONINTERACTIVE:-0}" != "1" ] && [ -t 1 ] && ! $GATE identity check --config "$CONFIG" --strict >/dev/null 2>&1; then
  say "Step 1 of 3: sign in with your Microsoft work account"
  $GATE identity login --config "$CONFIG" || say "Sign-in not completed; run 'ai-sdlc-gate identity login' later."
else
  $GATE identity check --config "$CONFIG" --strict >/dev/null 2>&1 && say "Step 1 of 3: already signed in" || say "Step 1 of 3: sign-in skipped (no terminal); run 'ai-sdlc-gate identity login' later."
fi

say "Step 2 of 3: installing the git hooks"
for h in commit-msg pre-push refresh-skills; do
  install -m 755 "$SDLC_HOME/repo/client/hooks/$h" "$SDLC_HOME/hooks/$h"
done
CURRENT_HOOKS="$(git config --global --get core.hooksPath || true)"
if [ -n "$CURRENT_HOOKS" ] && [ "$CURRENT_HOOKS" != "$SDLC_HOME/hooks" ]; then
  say "core.hooksPath is currently '$CURRENT_HOOKS'. It will be replaced; the gate chains to repository hooks itself."
fi
git config --global core.hooksPath "$SDLC_HOME/hooks"
# Repositories may set their own core.hooksPath (husky and friends). Git's environment override wins over
# repository configuration, so export it from the shell profiles; the gate chains to the project's hooks.
GIT_ENV_LINE="export GIT_CONFIG_PARAMETERS=\"'core.hooksPath=$SDLC_HOME/hooks'\" # ai-sdlc-gate"
for prof in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.zshenv"; do
  [ -f "$prof" ] || { case "$prof" in *".profile"|*".bashrc") touch "$prof";; *) continue;; esac; }
  grep -q "# ai-sdlc-gate" "$prof" 2>/dev/null && sed -i.bak '/# ai-sdlc-gate$/d' "$prof" && rm -f "$prof.bak"
  printf '%s\n' "$GIT_ENV_LINE" >> "$prof"
done

say "Step 3 of 3: preparing the review engine (uses your GitHub sign-in)"
if [ -n "${AI_SDLC_GATE_RECORD_FILE:-}" ] && [ -f "$AI_SDLC_GATE_RECORD_FILE" ]; then
  $GATE configure --config "$CONFIG" --import-record < "$AI_SDLC_GATE_RECORD_FILE" || say "The review engine could not be prepared yet; run 'ai-sdlc-gate configure' later."
else
  $GATE configure --config "$CONFIG" || say "The review engine could not be prepared yet; run 'ai-sdlc-gate configure' after signing in to GitHub (gh auth login)."
fi

say "Verifying"
$GATE validate-skills --config "$CONFIG" | tail -n 1
date +%s > "$SDLC_HOME/.last-refresh"

say "Done. Every commit and push on this machine now goes through the AI SDLC Gate."
