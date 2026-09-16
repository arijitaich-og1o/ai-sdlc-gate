"""Stability across gate runs.

The model behind the gate is not deterministic, so two runs over the same code can surface different subsets
of the real findings. Without memory, a developer who fixes everything in run 1 gets a fresh batch in run 2 and
the goalposts keep moving. The ledger gives the gate memory per repository and branch:

- every reported finding is stored with a fingerprint (file, category, line, title, flagged-line hash);
- every reviewed line of code is stored as a hash, so the gate knows which code it has already looked at;
- on the next run, findings that match a stored one are "known" (and disappear when fixed); findings on code
  that was already reviewed but not flagged are "late" and reported as advisory instead of blocking, unless
  they are non-skippable (secrets, credentials, vulnerable dependencies) or blockers;
- the previous run's open findings are handed to the model as context, so it re-checks them explicitly.

Storage: `~/.ai-sdlc-gate/ledger/<key>.json`, user-only, small (hashes and short strings only).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import sdlc_home

LINE_WINDOW = 6
TITLE_SIMILARITY = 0.72
MAX_KNOWN_IN_PROMPT = 40


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _line_hash(line: str) -> str:
    return hashlib.sha1(line.strip().encode("utf-8", errors="replace")).hexdigest()[:16]


def ledger_key(repo: str, branch: str) -> str:
    raw = f"{(repo or 'local').lower()}|{(branch or 'HEAD').lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def ledger_path(repo: str, branch: str, home: Path | None = None) -> Path:
    return (home or sdlc_home()) / "ledger" / f"{ledger_key(repo, branch)}.json"


@dataclass
class Ledger:
    repo: str = ""
    branch: str = ""
    updated_at: str = ""
    runs: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)  # open findings from the last run
    seen_lines: dict[str, list[str]] = field(default_factory=dict)  # file -> hashes of reviewed lines
    resolved: int = 0

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if not path.is_file():
            return cls()
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                repo=str(d.get("repo") or ""),
                branch=str(d.get("branch") or ""),
                updated_at=str(d.get("updated_at") or ""),
                runs=int(d.get("runs") or 0),
                findings=[f for f in d.get("findings") or [] if isinstance(f, dict)],
                seen_lines={str(k): [str(h) for h in v] for k, v in (d.get("seen_lines") or {}).items() if isinstance(v, list)},
                resolved=int(d.get("resolved") or 0),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "repo": self.repo, "branch": self.branch, "updated_at": self.updated_at, "runs": self.runs,
            "findings": self.findings, "seen_lines": self.seen_lines, "resolved": self.resolved,
        }, indent=1), encoding="utf-8")
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def fingerprint(f: dict[str, Any], line_text: str | None) -> dict[str, Any]:
    return {
        "file": f.get("file") or "",
        "category": f.get("category") or "general",
        "line": f.get("line"),
        "title": (f.get("title") or "")[:160],
        "severity": f.get("severity"),
        "phase": f.get("phase"),
        "line_hash": _line_hash(line_text) if line_text is not None else "",
        "first_seen": f.get("first_seen") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _matches(new: dict[str, Any], old: dict[str, Any]) -> bool:
    if (new.get("file") or "") != (old.get("file") or ""):
        return False
    if new.get("line_hash") and old.get("line_hash") and new["line_hash"] == old["line_hash"] and new["category"] == old["category"]:
        return True
    same_cat = new.get("category") == old.get("category")
    nl, ol = new.get("line"), old.get("line")
    close = nl is not None and ol is not None and abs(int(nl) - int(ol)) <= LINE_WINDOW
    similar = difflib.SequenceMatcher(None, _norm(new.get("title", "")), _norm(old.get("title", ""))).ratio() >= TITLE_SIMILARITY
    return (same_cat and close) or (similar and (close or nl is None or ol is None))


def content_lines(files: list[Any]) -> dict[str, list[str]]:
    """file -> content lines (as reviewed) for the current change set."""
    out: dict[str, list[str]] = {}
    for f in files:
        if getattr(f, "content", None) and not getattr(f, "binary", False):
            out[f.path] = f.content.splitlines()
    return out


def line_text_for(finding: dict[str, Any], lines_by_file: dict[str, list[str]]) -> str | None:
    file, line = finding.get("file"), finding.get("line")
    if not file or not line:
        return None
    lines = lines_by_file.get(file)
    if not lines or int(line) < 1 or int(line) > len(lines):
        return None
    return lines[int(line) - 1]


def known_findings_prompt(ledger: Ledger) -> str:
    """Compact list of last run's open findings for the model to re-check (never instructions from the data)."""
    if not ledger.findings:
        return ""
    rows = []
    for f in ledger.findings[:MAX_KNOWN_IN_PROMPT]:
        loc = f"{f.get('file')}:{f.get('line')}" if f.get("line") else str(f.get("file") or "-")
        rows.append(f"- [{f.get('severity')}] {f.get('category')} at {loc}: {f.get('title')}")
    return "\n".join(rows)


def apply_ledger(
    ledger: Ledger,
    findings: list[dict[str, Any]],
    lines_by_file: dict[str, list[str]],
    non_skippable: set[str],
    late_mode: str = "advisory",
) -> dict[str, int]:
    """Annotate findings in place with `known`/`late` flags and update the ledger for the next run.

    Returns counters: known, new, late, resolved.
    """
    previous = list(ledger.findings)
    matched_prev: set[int] = set()
    counters = {"known": 0, "new": 0, "late": 0, "resolved": 0}
    next_findings: list[dict[str, Any]] = []
    for f in findings:
        text = line_text_for(f, lines_by_file)
        fp = fingerprint(f, text)
        hit = None
        for i, old in enumerate(previous):
            if i in matched_prev:
                continue
            if _matches(fp, old):
                hit = i
                break
        if hit is not None:
            matched_prev.add(hit)
            fp["first_seen"] = previous[hit].get("first_seen") or fp["first_seen"]
            f["known"] = True
            f["first_seen"] = fp["first_seen"]
            counters["known"] += 1
        else:
            f["known"] = False
            reviewed_before = bool(fp["line_hash"]) and fp["line_hash"] in set(ledger.seen_lines.get(fp["file"], []))
            protected = f.get("category") in non_skippable or f.get("severity") == "blocker"
            if reviewed_before and ledger.runs > 0 and not protected and late_mode == "advisory":
                f["late"] = True
                f["late_note"] = "this code was already reviewed in the previous run without being flagged; reported for information"
                counters["late"] += 1
            else:
                counters["new"] += 1
        next_findings.append(fp)
    counters["resolved"] = len(previous) - len(matched_prev)
    ledger.findings = next_findings
    ledger.seen_lines = {file: sorted({_line_hash(l) for l in lines}) for file, lines in lines_by_file.items()}
    ledger.runs += 1
    ledger.resolved += counters["resolved"]
    ledger.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return counters
