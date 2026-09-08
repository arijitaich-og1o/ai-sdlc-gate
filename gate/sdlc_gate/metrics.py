"""Metrics: build compact events from gate reports, ship them to the central repository,
ingest them on a dedicated branch, and build a management dashboard.

Event storage layout (on the `metrics` branch of the central repository):

    events/YYYY/MM.jsonl     one JSON object per line, deduplicated by `id`
    dashboard/README.md      human dashboard (org, per repository, per developer, trends)
    dashboard/summary.json   machine-readable snapshot for BI tooling
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import SEVERITIES, severity_rank
from .runner import GateReport

MAX_PAYLOAD_BYTES = 60_000
MAX_BRIEF = 40
REQUIRED_EVENT_KEYS = {"schema": int, "id": str, "ts": str, "repo": str, "actor": str, "verdict": str, "intent": str, "phases": list}
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def build_event(report: GateReport) -> dict[str, Any]:
    ctx = report.context or {}
    findings = report.all_findings()
    counts = {s: 0 for s in SEVERITIES}
    waived = 0
    for f in findings:
        counts[f["severity"]] += 1
        if f.get("waived"):
            waived += 1
    thr = severity_rank(report.threshold)
    flagged = any(severity_rank(f["severity"]) >= thr for f in findings)
    brief = [
        {
            "phase": f.get("phase"),
            "severity": f["severity"],
            "category": f["category"],
            "title": f["title"][:120],
            "file": (f.get("file") or "")[:160],
            "waived": bool(f.get("waived")),
        }
        for f in sorted(findings, key=lambda x: -severity_rank(x["severity"]))[:MAX_BRIEF]
    ]
    cats = Counter(f["category"] for f in findings)
    event = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "ts": report.generated_at,
        "repo": str(ctx.get("repo") or "unknown/unknown"),
        "actor": str(ctx.get("actor") or ctx.get("author_name") or "unknown"),
        "author_email": str(ctx.get("author_email") or "")[:200],
        "ref": str(ctx.get("ref") or "")[:200],
        "sha": str(ctx.get("sha") or report.stats.get("head") or "")[:64],
        "event_name": str(ctx.get("event_name") or "")[:40],
        "pr_number": ctx.get("pr_number"),
        "run_id": str(ctx.get("run_id") or "")[:40],
        "run_url": str(ctx.get("run_url") or "")[:300],
        "intent": report.intent.intent,
        "intent_source": report.intent.source,
        "phases": list(report.intent.phases),
        "verdict": report.verdict,
        "flagged": flagged,
        "blocked": report.verdict == "fail",
        "threshold": report.threshold,
        "counts": counts,
        "waived_count": waived,
        "findings_total": len(findings),
        "skip": {
            "requested": report.skip.requested,
            "valid": report.skip.valid,
            "requested_phases": report.skip.requested_phases,
            "valid_phases": report.skip.valid_phases,
            "reason": (report.skip.reason or "")[:500],
            "errors": [e[:200] for e in report.skip.errors][:5],
        },
        "phase_results": [
            {"phase": p.phase, "verdict": p.verdict, "counts": p.counts(), "skill_version": p.skill_version, "error": bool(p.error)}
            for p in report.phases
        ],
        "top_categories": [c for c, _ in cats.most_common(8)],
        "findings_brief": brief,
        "files": int(report.stats.get("files", 0)),
        "llm_usage": report.llm_usage,
        "duration_s": round(sum(p.duration_s for p in report.phases), 1),
    }
    return shrink_event(event)


def shrink_event(event: dict[str, Any]) -> dict[str, Any]:
    while len(json.dumps(event, separators=(",", ":")).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        if event.get("findings_brief"):
            event["findings_brief"] = event["findings_brief"][: max(0, len(event["findings_brief"]) // 2)]
        elif event["skip"].get("reason"):
            event["skip"]["reason"] = event["skip"]["reason"][:100]
        else:
            break
    return event


def dispatch_event(event: dict[str, Any], repo: str, token: str, event_type: str, api_base: str = "https://api.github.com") -> None:
    if not REPO_RE.match(repo):
        raise ValueError(f"invalid repository slug: {repo!r}")
    if not token:
        raise ValueError("a GitHub token with `contents: write` on the central repository is required to dispatch metrics")
    resp = httpx.post(
        f"{api_base}/repos/{repo}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sdlc-gate/1.0",
        },
        json={"event_type": event_type, "client_payload": {"event": event}},
        timeout=30,
    )
    if resp.status_code not in (204, 200):
        raise RuntimeError(f"repository_dispatch failed: HTTP {resp.status_code}: {resp.text[:300]}")


# ----------------------------------------------------------------------------- ingest

def validate_event(event: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return ["event must be an object"]
    for key, typ in REQUIRED_EVENT_KEYS.items():
        if key not in event:
            errors.append(f"missing `{key}`")
        elif not isinstance(event[key], typ):
            errors.append(f"`{key}` must be {typ.__name__}")
    if errors:
        return errors
    if event["schema"] != 1:
        errors.append("unsupported schema version")
    if not re.match(r"^[0-9a-f-]{36}$", event["id"]):
        errors.append("`id` must be a UUID")
    if not REPO_RE.match(event["repo"]):
        errors.append("`repo` must be owner/name")
    if not LOGIN_RE.match(event["actor"]):
        errors.append("`actor` is not a valid GitHub login")
    if event["verdict"] not in ("pass", "fail"):
        errors.append("`verdict` must be pass or fail")
    try:
        datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
    except ValueError:
        errors.append("`ts` must be ISO-8601")
    if len(json.dumps(event).encode("utf-8")) > MAX_PAYLOAD_BYTES + 4096:
        errors.append("event too large")
    return errors


def ingest_event(event: dict[str, Any], events_dir: Path) -> tuple[Path, bool]:
    """Append the event to its monthly file. Returns (path, written)."""
    errors = validate_event(event)
    if errors:
        raise ValueError("invalid metrics event: " + "; ".join(errors))
    ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
    path = events_dir / f"{ts.year:04d}" / f"{ts.month:02d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if f'"id": "{event["id"]}"' in line or f'"id":"{event["id"]}"' in line:
                    return path, False
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return path, True


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not events_dir.is_dir():
        return events
    for path in sorted(events_dir.rglob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not validate_event(ev):
                    events.append(ev)
    events.sort(key=lambda e: e["ts"])
    return events


# ----------------------------------------------------------------------------- dashboard

def _bucket() -> dict[str, Any]:
    return {
        "runs": 0,
        "passed": 0,
        "flagged": 0,
        "blocked": 0,
        "skips_requested": 0,
        "skips_granted": 0,
        "waived_findings": 0,
        "findings": {s: 0 for s in SEVERITIES},
        "categories": Counter(),
        "intents": Counter(),
        "first_seen": None,
        "last_seen": None,
        "repos": set(),
        "actors": set(),
    }


def _add(b: dict[str, Any], e: dict[str, Any]) -> None:
    b["runs"] += 1
    b["passed"] += 1 if e["verdict"] == "pass" else 0
    b["flagged"] += 1 if e.get("flagged") else 0
    b["blocked"] += 1 if e.get("blocked") else 0
    sk = e.get("skip") or {}
    b["skips_requested"] += 1 if sk.get("requested") else 0
    b["skips_granted"] += 1 if sk.get("valid") else 0
    b["waived_findings"] += int(e.get("waived_count") or 0)
    for s, n in (e.get("counts") or {}).items():
        if s in b["findings"]:
            b["findings"][s] += int(n or 0)
    b["categories"].update(e.get("top_categories") or [])
    b["intents"][e.get("intent", "?")] += 1
    b["first_seen"] = min(b["first_seen"] or e["ts"], e["ts"])
    b["last_seen"] = max(b["last_seen"] or e["ts"], e["ts"])
    b["repos"].add(e["repo"])
    b["actors"].add(e["actor"])


def _finalize(b: dict[str, Any]) -> dict[str, Any]:
    runs = b["runs"] or 1
    return {
        "runs": b["runs"],
        "passed": b["passed"],
        "pass_rate": round(b["passed"] / runs, 3),
        "flagged": b["flagged"],
        "flag_rate": round(b["flagged"] / runs, 3),
        "blocked": b["blocked"],
        "block_rate": round(b["blocked"] / runs, 3),
        "skips_requested": b["skips_requested"],
        "skips_granted": b["skips_granted"],
        "skip_rate": round(b["skips_granted"] / runs, 3),
        "waived_findings": b["waived_findings"],
        "findings": b["findings"],
        "findings_per_run": round(sum(b["findings"].values()) / runs, 2),
        "top_categories": [c for c, _ in b["categories"].most_common(5)],
        "intents": dict(b["intents"]),
        "first_seen": b["first_seen"],
        "last_seen": b["last_seen"],
        "repos": sorted(b["repos"]),
        "actors_count": len(b["actors"]),
    }


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    org = _bucket()
    by_dev: dict[str, dict[str, Any]] = defaultdict(_bucket)
    by_repo: dict[str, dict[str, Any]] = defaultdict(_bucket)
    by_month: dict[str, dict[str, Any]] = defaultdict(_bucket)
    for e in events:
        _add(org, e)
        _add(by_dev[e["actor"]], e)
        _add(by_repo[e["repo"]], e)
        _add(by_month[e["ts"][:7]], e)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": len(events),
        "organisation": _finalize(org),
        "developers": {k: _finalize(v) for k, v in sorted(by_dev.items())},
        "repositories": {k: _finalize(v) for k, v in sorted(by_repo.items())},
        "months": {k: _finalize(v) for k, v in sorted(by_month.items())},
    }


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def dashboard_markdown(summary: dict[str, Any]) -> str:
    org = summary["organisation"]
    L: list[str] = []
    L.append("# SDLC Gate — Organisation Dashboard")
    L.append("")
    L.append(f"_Generated {summary['generated_at']} from {summary['events']} gate run(s)._")
    L.append("")
    L.append("## Organisation snapshot")
    L.append("")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Gate runs | {org['runs']} |")
    L.append(f"| Pass rate | {_pct(org['pass_rate'])} |")
    L.append(f"| Runs flagged (findings at/above threshold) | {org['flagged']} ({_pct(org['flag_rate'])}) |")
    L.append(f"| Runs blocked | {org['blocked']} ({_pct(org['block_rate'])}) |")
    L.append(f"| Skips requested / granted | {org['skips_requested']} / {org['skips_granted']} |")
    L.append(f"| Findings waived via skips | {org['waived_findings']} |")
    L.append(f"| Findings per run | {org['findings_per_run']} |")
    L.append(f"| Active developers / repositories | {org['actors_count']} / {len(org['repos'])} |")
    L.append(f"| Top finding categories | {', '.join(org['top_categories']) or '-'} |")
    L.append("")
    L.append("## Monthly trend")
    L.append("")
    L.append("| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m, b in summary["months"].items():
        L.append(f"| {m} | {b['runs']} | {_pct(b['pass_rate'])} | {b['blocked']} | {b['skips_granted']} | {b['findings']['blocker']} | {b['findings']['high']} | {b['findings']['medium']} |")
    L.append("")
    L.append("## Developers")
    L.append("")
    L.append("| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Top categories | Last seen |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for dev, b in sorted(summary["developers"].items(), key=lambda kv: -kv[1]["runs"]):
        L.append(
            f"| @{dev} | {b['runs']} | {_pct(b['pass_rate'])} | {b['flagged']} | {b['blocked']} | {b['skips_requested']}/{b['skips_granted']} "
            f"| {b['waived_findings']} | {b['findings_per_run']} | {', '.join(b['top_categories'][:3]) or '-'} | {b['last_seen'][:10]} |"
        )
    L.append("")
    L.append("## Repositories")
    L.append("")
    L.append("| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |")
    L.append("|---|---|---|---|---|---|---|---|")
    for repo, b in sorted(summary["repositories"].items(), key=lambda kv: -kv[1]["runs"]):
        L.append(f"| {repo} | {b['runs']} | {_pct(b['pass_rate'])} | {b['blocked']} | {b['skips_granted']} | {b['actors_count']} | {b['findings_per_run']} | {', '.join(b['top_categories'][:3]) or '-'} |")
    L.append("")
    L.append("### Reading this dashboard")
    L.append("")
    L.append("- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.")
    L.append("- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.")
    L.append("- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.")
    L.append("- Per-developer numbers reflect the GitHub account that triggered the run; they are a quality signal, not a performance score on their own.")
    return "\n".join(L) + "\n"


def build_dashboard(events_dir: Path, out_dir: Path) -> dict[str, Any]:
    events = load_events(events_dir)
    summary = summarize(events)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "README.md").write_text(dashboard_markdown(summary), encoding="utf-8")
    return summary
