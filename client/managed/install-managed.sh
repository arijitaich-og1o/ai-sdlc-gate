#!/usr/bin/env bash
# SDLC Gate — MANAGED client install for Linux / macOS / WSL (run as root, typically from MDM: Intune, Jamf, Ansible).
#
# Compared with the per-user installer this puts everything where a non-administrator cannot change it:
#   /opt/sdlc-gate/repo      engine, skills and policy (root-owned, refreshed by a root cron/launchd job)
#   /opt/sdlc-gate/venv      isolated Python with the sdlc-gate CLI
#   /opt/sdlc-gate/hooks     git hooks (commit-msg, pre-push)
#   /opt/sdlc-gate/bin/git   a git shim that strips --no-verify / -n on commit, removes user overrides of
#                            core.hooksPath, and forces the managed hooks path for every invocation
#   system gitconfig         core.hooksPath -> managed hooks, sdlc-gate.managed=true (hooks fail closed and
#                            require a verified identity)
#   /etc/profile.d           puts /opt/sdlc-gate/bin first in PATH for login shells
#
# Each developer still runs `sdlc-gate identity login` once (their own Entra sign-in) and stores their own
# LiteLLM key in ~/.sdlc-gate/env; the managed layer never contains per-user secrets.
#
# Limits (read docs/enforcement.md): a user with root/sudo can remove any of this. The GitHub ruleset remains the
# guarantee; the managed client makes local bypass loud and inconvenient, and every bypass is visible in metrics.
set -euo pipefail

REPO_URL="${SDLC_GATE_REPO_URL:-https://github.com/arijitaich-og1o/ai-sdlc-gate.git}"
REF="${SDLC_GATE_REF:-main}"
PREFIX="${SDLC_GATE_PREFIX:-/opt/sdlc-gate}"

[ "$(id -u)" = "0" ] || { echo "run as root (sudo)"; exit 1; }
command -v git >/dev/null || { echo "git is required"; exit 1; }
PY=""; for c in python3 python; do command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "Python 3.10+ is required"; exit 1; }

REAL_GIT="$(command -v git)"
case "$REAL_GIT" in "$PREFIX"/*) REAL_GIT="$(cat "$PREFIX/bin/.real-git" 2>/dev/null || echo /usr/bin/git)";; esac

umask 022
mkdir -p "$PREFIX/bin" "$PREFIX/hooks"
if [ -d "$PREFIX/repo/.git" ]; then
  git -C "$PREFIX/repo" fetch --quiet --depth 1 origin "$REF" && git -C "$PREFIX/repo" reset --quiet --hard FETCH_HEAD
else
  rm -rf "$PREFIX/repo"; git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$PREFIX/repo"
fi
printf '%s\n' "$REF" > "$PREFIX/ref"

[ -x "$PREFIX/venv/bin/python" ] || "$PY" -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/python" -m pip install --quiet --upgrade pip "$PREFIX/repo/gate"
ln -sf "$PREFIX/venv/bin/sdlc-gate" "$PREFIX/bin/sdlc-gate"

for h in commit-msg pre-push refresh-skills; do install -m 755 "$PREFIX/repo/client/hooks/$h" "$PREFIX/hooks/$h"; done

printf '%s\n' "$REAL_GIT" > "$PREFIX/bin/.real-git"
cat > "$PREFIX/bin/git" <<'SHIM'
#!/usr/bin/env bash
# SDLC Gate managed git shim: enforces the managed hooks path and removes hook-bypass flags.
PREFIX="/opt/sdlc-gate"
REAL_GIT="$(cat "$PREFIX/bin/.real-git" 2>/dev/null || echo /usr/bin/git)"
unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
for v in $(env | grep -o '^GIT_CONFIG_KEY_[0-9]*' ; env | grep -o '^GIT_CONFIG_VALUE_[0-9]*'); do unset "$v"; done
args=(); sub=""; skip_next=0
for a in "$@"; do
  if [ "$skip_next" = 1 ]; then skip_next=0; case "$a" in core.hooksPath=*|core.hookspath=*|sdlc-gate.*) continue;; esac; args+=("-c" "$a"); continue; fi
  case "$a" in
    -c) skip_next=1; continue;;
    -c=*|--config-env=*) case "${a#*=}" in core.hooksPath*|core.hookspath*|sdlc-gate.*) continue;; esac;;
  esac
  if [ -z "$sub" ] && [[ "$a" != -* ]]; then sub="$a"; fi
  case "$sub" in
    commit|merge|rebase|push|cherry-pick|revert)
      case "$a" in --no-verify) continue;; esac
      [ "$sub" = commit ] && [ "$a" = "-n" ] && continue
      ;;
  esac
  args+=("$a")
done
exec "$REAL_GIT" -c "core.hooksPath=$PREFIX/hooks" "${args[@]}"
SHIM
sed -i.bak "s#^PREFIX=.*#PREFIX=\"$PREFIX\"#" "$PREFIX/bin/git" && rm -f "$PREFIX/bin/git.bak"
chmod 755 "$PREFIX/bin/git"

git config --system core.hooksPath "$PREFIX/hooks"
git config --system sdlc-gate.managed true
git config --system sdlc-gate.prefix "$PREFIX"

if [ -d /etc/profile.d ]; then
  printf 'export PATH="%s/bin:$PATH"\nexport SDLC_GATE_REPO="%s/repo"\n' "$PREFIX" "$PREFIX" > /etc/profile.d/sdlc-gate.sh
fi
if [ -d /etc/paths.d ]; then printf '%s/bin\n' "$PREFIX" > /etc/paths.d/00-sdlc-gate; fi
if [ -f /etc/zshenv ] || [ "$(uname)" = "Darwin" ]; then
  grep -q sdlc-gate /etc/zshenv 2>/dev/null || printf '\nexport PATH="%s/bin:$PATH"\nexport SDLC_GATE_REPO="%s/repo"\n' "$PREFIX" "$PREFIX" >> /etc/zshenv
fi

# Daily refresh of skills/policy as root.
cat > "$PREFIX/bin/refresh-managed" <<EOF
#!/usr/bin/env bash
set -e
git -C "$PREFIX/repo" fetch --quiet --depth 1 origin "\$(cat "$PREFIX/ref")" && git -C "$PREFIX/repo" reset --quiet --hard FETCH_HEAD
"$PREFIX/venv/bin/python" -m pip install --quiet --upgrade "$PREFIX/repo/gate"
for h in commit-msg pre-push refresh-skills; do install -m 755 "$PREFIX/repo/client/hooks/\$h" "$PREFIX/hooks/\$h"; done
EOF
chmod 755 "$PREFIX/bin/refresh-managed"
if [ -d /etc/cron.daily ]; then ln -sf "$PREFIX/bin/refresh-managed" /etc/cron.daily/sdlc-gate; fi
if [ "$(uname)" = "Darwin" ]; then
  cat > /Library/LaunchDaemons/in.og1o.sdlc-gate.refresh.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>in.og1o.sdlc-gate.refresh</string>
  <key>ProgramArguments</key><array><string>$PREFIX/bin/refresh-managed</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>15</integer></dict>
</dict></plist>
EOF
  launchctl load -w /Library/LaunchDaemons/in.og1o.sdlc-gate.refresh.plist 2>/dev/null || true
fi

"$PREFIX/bin/sdlc-gate" validate-skills --config "$PREFIX/repo/gate.config.yaml"
echo "[sdlc-gate] managed install complete at $PREFIX. Developers: run 'sdlc-gate identity login' and store their LiteLLM key with 'sdlc-gate configure'."
