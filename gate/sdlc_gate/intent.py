"""Determine what the developer is doing (intent) and which SDLC phases apply."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .changes import matches_any
from .config import Config


@dataclass
class IntentDecision:
    intent: str
    phases: list[int]
    source: str  # explicit | trailer | branch | paths | default
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"intent": self.intent, "phases": self.phases, "source": self.source, "notes": self.notes}


def _trailer_values(messages: list[str], key: str) -> list[str]:
    pat = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", re.I | re.M)
    vals: list[str] = []
    for m in messages:
        vals.extend(pat.findall(m))
    return vals


_CODE_EXT = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".swift", ".scala", ".sql", ".sh", ".ps1",
)


def _has_code(paths: list[str]) -> bool:
    return any(p.lower().endswith(_CODE_EXT) for p in paths)


def detect_intent(
    cfg: Config,
    explicit: str | None = None,
    commit_messages: list[str] | None = None,
    branch: str | None = None,
    paths: list[str] | None = None,
) -> IntentDecision:
    intents = cfg.intents
    det = cfg.intent_detection
    notes: list[str] = []

    def finish(intent: str, source: str) -> IntentDecision:
        if intent not in intents:
            raise ValueError(f"Unknown intent {intent!r}; allowed: {', '.join(sorted(intents))}")
        return IntentDecision(intent=intent, phases=sorted(set(intents[intent])), source=source, notes=notes)

    if explicit:
        return finish(explicit.strip().lower(), "explicit")

    trailer_key = det.get("trailer", "SDLC-Intent")
    for val in _trailer_values(commit_messages or [], trailer_key):
        candidate = val.strip().lower()
        if candidate in intents:
            return finish(candidate, "trailer")
        notes.append(f"ignored unknown {trailer_key} trailer value {val!r}")

    if branch:
        for rule in det.get("branch_patterns") or []:
            if re.search(rule["pattern"], branch, re.I):
                notes.append(f"branch {branch!r} matched /{rule['pattern']}/")
                return finish(rule["intent"], "branch")

    if paths:
        votes: dict[str, int] = {}
        for rule in det.get("path_patterns") or []:
            globs = rule.get("glob") or []
            if isinstance(globs, str):
                globs = [globs]
            hits = [p for p in paths if matches_any(p, globs)]
            if hits:
                votes[rule["intent"]] = votes.get(rule["intent"], 0) + len(hits)
        if votes:
            # Highest-coverage intent wins; broader intents win ties.
            ranked = sorted(votes.items(), key=lambda kv: (kv[1], len(intents[kv[0]])), reverse=True)
            intent = ranked[0][0]
            notes.append(f"path heuristics voted {votes}")
            default = det.get("default", "commit")
            phases = set(intents[intent])
            if _has_code(paths):
                # Never narrow below the default when code files are also present.
                phases |= set(intents[default])
            return IntentDecision(intent=intent, phases=sorted(phases), source="paths", notes=notes)

    return finish(det.get("default", "commit"), "default")
