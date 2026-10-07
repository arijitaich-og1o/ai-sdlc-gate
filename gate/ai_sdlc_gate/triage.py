"""Finding triage: a developer labels a finding of the last gate run as accepted, a false positive or won't fix.

Labels are stored on the developer's machine (`<gate home>/triage.jsonl`) and travel to the organisation metrics
with the next gate run's event (`emit-metrics`), marked sent only after that dispatch succeeds. What leaves the
machine is only the phase, category, severity, label and the run's timestamp: never the finding's title, file,
line or the developer's note. That is enough for a false-positive rate per phase and category.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LABELS = ("accepted", "false-positive", "wont-fix")
MAX_PER_EVENT = 100  # keeps the event well inside its 60 KB budget; the rest goes with the next run


def triage_path(home: Path) -> Path:
    return home / "triage.jsonl"


def report_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The findings of a gate report in display order (phase, then as reported), numbered from 1."""
    out = []
    for ph in report.get("phases") or []:
        for f in ph.get("findings") or []:
            out.append({**f, "phase": f.get("phase", ph.get("phase"))})
    for i, f in enumerate(out, start=1):
        f["n"] = i
    return out


def load(home: Path) -> list[dict[str, Any]]:
    path = triage_path(home)
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and e.get("label") in LABELS:
            entries.append(e)
    return entries


def _save(home: Path, entries: list[dict[str, Any]]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    path = triage_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in entries), encoding="utf-8")
    tmp.replace(path)


def record(home: Path, report: dict[str, Any], finding: dict[str, Any], label: str, note: str = "") -> dict[str, Any]:
    """Label one finding of `report`. A new label for the same finding replaces an unsent one."""
    if label not in LABELS:
        raise ValueError(f"label must be one of {', '.join(LABELS)}")
    run_ts = str(report.get("generated_at") or "")
    key = (run_ts, str(finding.get("id") or ""), int(finding.get("phase") or 0))
    entries = [
        e for e in load(home)
        if e.get("sent") or (e.get("run_ts"), e.get("finding_id"), int(e.get("phase") or 0)) != key
    ]
    entry = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_ts": run_ts,
        "finding_id": key[1],
        "phase": key[2],
        "category": str(finding.get("category") or "general"),
        "severity": str(finding.get("severity") or "info"),
        "label": label,
        "note": note[:500],  # local only, never sent
        "sent": False,
    }
    entries.append(entry)
    _save(home, entries)
    return entry


def pending(home: Path) -> list[dict[str, Any]]:
    return [e for e in load(home) if not e.get("sent")][:MAX_PER_EVENT]


def for_event(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What goes into the metrics event: no finding id, title, file, line or note."""
    return [
        {"phase": int(e.get("phase") or 0), "category": e["category"], "severity": e["severity"], "label": e["label"], "run_ts": e.get("run_ts", "")}
        for e in entries
    ]


def mark_sent(home: Path, ids: list[str]) -> None:
    if not ids:
        return
    sent = set(ids)
    entries = load(home)
    for e in entries:
        if e.get("id") in sent:
            e["sent"] = True
    _save(home, entries)
