#!/usr/bin/env bash
# SDLC Gate developer installer (Linux, macOS, WSL, Git Bash).
#
#   curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash
#
# What it does
#   1. clones (or refreshes) the central repository to ~/.sdlc-gate/repo
#   2. installs the `sdlc-gate` CLI for the current user (pipx if available, else pip --user)
#   3. installs global git hooks (commit-msg, pre-push) via core.hooksPath, chaining to repo-local hooks
#   4. stores the LiteLLM endpoint + key in ~/.sdlc-gate/env (mode 600)
#
# Environment overrides: SDLC_GATE_REPO_URL, SDLC_GATE_REF, LITELLM_BASE_URL, LITELLM_API_KEY, SDLC_GATE_HOME
set -euo pipefail

REPO_URL="${SDLC_GATE_REPO_URL:-https://github.com/arijitaich-og1o/ai-sdlc-gate.git}"
REF="${SDLC_GATE_REF:-main}"
SDLC_HOME="${SDLC_GATE_HOME:-$HOME/.sdlc-gate}"
DEFAULT_BASE_URL="https://litellm-dev.dev.aime.osp-fine.de"

say() { printf '\033[1;34m[sdlc-gate]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[sdlc-gate] %s\033[0m\n' "$*" >&2; exit 1; }

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

say "Installing the sdlc-gate CLI"
if command -v pipx >/dev/null 2>&1; then
  pipx install --force --quiet "$SDLC_HOME/repo/gate" >/dev/null
else
  "$PY" -m pip install --quiet --user --upgrade "$SDLC_HOME/repo/gate"
  USER_BIN="$("$PY" -c 'import sysconfig; print(sysconfig.get_path("scripts", "posix_user" if __import__("os").name != "nt" else "nt_user"))' 2>/dev/null || true)"
  if [ -n "$USER_BIN" ] && ! command -v sdlc-gate >/dev/null 2>&1; then
    say "Add $USER_BIN to your PATH so git hooks can find sdlc-gate"
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

if [ ! -f "$SDLC_HOME/env" ] || [ -n "${LITELLM_API_KEY:-}" ]; then
  BASE_URL="${LITELLM_BASE_URL:-$DEFAULT_BASE_URL}"
  KEY="${LITELLM_API_KEY:-}"
  if [ -z "$KEY" ] && [ -t 0 ]; then
    printf 'LiteLLM API key (input hidden, stored in %s): ' "$SDLC_HOME/env"
    read -rs KEY; echo
  fi
  if [ -n "$KEY" ]; then
    umask 077
    { printf 'export LITELLM_BASE_URL=%q\n' "$BASE_URL"; printf 'export LITELLM_API_KEY=%q\n' "$KEY"; } > "$SDLC_HOME/env"
    chmod 600 "$SDLC_HOME/env"
    say "Stored LiteLLM configuration in $SDLC_HOME/env"
  else
    say "No LiteLLM key provided; local hooks will skip the model review until $SDLC_HOME/env exists."
  fi
fi
date +%s > "$SDLC_HOME/.last-refresh"

say "Verifying"
if command -v sdlc-gate >/dev/null 2>&1; then
  sdlc-gate validate-skills --config "$SDLC_HOME/repo/gate.config.yaml"
fi
say "Done. Every commit and push on this machine now runs the SDLC Gate locally; GitHub enforces it centrally."
