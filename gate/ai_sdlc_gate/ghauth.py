"""Locate a GitHub credential on the developer's machine for sending metrics.

Developers already authenticate to GitHub to push code. We reuse that credential, never store it, and only use
it for one call: `repository_dispatch` to the central repository (which requires write access there, the same
access needed to open a skill challenge). Order of precedence:

1. `AI_SDLC_GATE_TOKEN` environment variable (CI and power users)
2. `gh auth token` (GitHub CLI)
3. the git credential helper (`git credential fill`), e.g. Git Credential Manager on Windows/macOS
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


@dataclass
class GitHubCredential:
    token: str
    username: str = ""
    source: str = ""


def _run(cmd: list[str], stdin: str | None = None, timeout: int = 15) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "echo"}
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    return proc.stdout if proc.returncode == 0 else ""


def find_credential(host: str = "github.com", token_env: str = "AI_SDLC_GATE_TOKEN") -> GitHubCredential | None:
    env_token = os.environ.get(token_env, "").strip()
    if env_token:
        return GitHubCredential(token=env_token, username=os.environ.get("GITHUB_ACTOR", ""), source="env")
    try:
        token = _run(["gh", "auth", "token", "--hostname", host]).strip()
        if token:
            login = _run(["gh", "api", "user", "--jq", ".login"]).strip()
            return GitHubCredential(token=token, username=login if LOGIN_RE.match(login) else "", source="gh")
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        out = _run(["git", "credential", "fill"], stdin=f"protocol=https\nhost={host}\n\n")
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    fields = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    token = fields.get("password", "").strip()
    if token:
        user = fields.get("username", "").strip()
        return GitHubCredential(token=token, username=user if LOGIN_RE.match(user) else "", source="git-credential")
    return None
