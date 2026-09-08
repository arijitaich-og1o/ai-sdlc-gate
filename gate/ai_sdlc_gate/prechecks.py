"""Deterministic checks that run before (and independently of) the model review.

These produce findings that are never skippable: leaked credentials, private keys,
and committed environment files. They are cheap, fast, and do not depend on the model gateway.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .changes import ChangeSet
from .config import Config

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe key", re.compile(r"\b(sk|rk)_(live|test)_[0-9a-zA-Z]{20,}\b")),
    ("OpenAI/model gateway style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("Azure storage key", re.compile(r"AccountKey=[A-Za-z0-9+/=]{60,}")),
    (
        "Hard-coded password assignment",
        re.compile(r"(?i)[A-Za-z0-9_.]*(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)[A-Za-z0-9_]*\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
    ),
    ("Connection string with credentials", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s]{4,}@[^\s\"']+")),
]

PLACEHOLDER_HINTS = re.compile(
    r"(?i)(example|placeholder|dummy|changeme|change_me|your[_-]?(key|token|password|secret)|<[^>]+>|\$\{[^}]+\}|\{\{[^}]+\}\}"
    r"|[\"']\{[A-Za-z_][A-Za-z0-9_.]*\}[\"']|xxxx|\*\*\*\*|redacted|not[_-]?a[_-]?real)"
)
ENV_FILE = re.compile(r"(^|/)\.env(\.[A-Za-z0-9_-]+)?$")
ENV_FILE_ALLOW = re.compile(r"(^|/)\.env\.(example|sample|template|dist)$")


@dataclass
class Precheck:
    category: str
    severity: str
    title: str
    description: str
    file: str
    line: int | None
    recommendation: str
    rule: str

    def to_finding(self) -> dict:
        return {
            "id": f"precheck-{self.rule}",
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "file": self.file,
            "line": self.line,
            "recommendation": self.recommendation,
            "confidence": 0.95,
            "source": "precheck",
        }


def _added_lines(diff: str, content: str | None) -> list[tuple[int | None, str]]:
    """Return (line_no, text) for added lines from the diff; fall back to full content."""
    out: list[tuple[int | None, str]] = []
    if diff:
        new_ln = 0
        for raw in diff.splitlines():
            if raw.startswith("@@"):
                m = re.search(r"\+(\d+)", raw)
                new_ln = int(m.group(1)) - 1 if m else 0
                continue
            if raw.startswith("+++") or raw.startswith("---"):
                continue
            if raw.startswith("+"):
                new_ln += 1
                out.append((new_ln, raw[1:]))
            elif raw.startswith("-"):
                continue
            else:
                new_ln += 1
        if out:
            return out
    if content:
        return [(i + 1, line) for i, line in enumerate(content.splitlines())]
    return out


def run_prechecks(cfg: Config, cs: ChangeSet) -> list[dict]:
    if not cfg.prechecks.get("enabled", True):
        return []
    allow = [re.compile(p) for p in cfg.prechecks.get("secret_allow_regexes") or []]
    findings: list[dict] = []
    for f in cs.files:
        if f.status == "D" or f.binary:
            continue
        if ENV_FILE.search(f.path) and not ENV_FILE_ALLOW.search(f.path):
            findings.append(
                Precheck(
                    category="secret-exposure",
                    severity="blocker",
                    title="Environment file committed",
                    description=f"`{f.path}` looks like a dotenv file. These typically contain credentials and must not be versioned.",
                    file=f.path,
                    line=None,
                    recommendation="Remove the file from the commit, add it to .gitignore, and provide a `.env.example` with placeholder values instead.",
                    rule="env-file",
                ).to_finding()
            )
        seen_rules: set[tuple[str, int | None]] = set()
        for line_no, text in _added_lines(f.diff, f.content):
            if "ai-sdlc-gate: allow-secret" in text:
                continue
            for label, pat in SECRET_PATTERNS:
                m = pat.search(text)
                if not m:
                    continue
                token = m.group(0)
                if PLACEHOLDER_HINTS.search(token) or PLACEHOLDER_HINTS.search(text):
                    continue
                if any(a.search(text) for a in allow):
                    continue
                key = (label, line_no)
                if key in seen_rules:
                    continue
                seen_rules.add(key)
                redacted = token[:6] + "..." + token[-3:] if len(token) > 12 else "..."
                findings.append(
                    Precheck(
                        category="hardcoded-credential" if label.startswith("Hard-coded") else "secret-exposure",
                        severity="blocker",
                        title=f"{label} detected",
                        description=f"A value matching the pattern for `{label}` was added ({redacted}).",
                        file=f.path,
                        line=line_no,
                        recommendation="Remove the secret from the code, rotate it immediately, and load it from a secret manager or environment variable.",
                        rule=re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"),
                    ).to_finding()
                )
    return findings
