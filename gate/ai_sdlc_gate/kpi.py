"""KPI dataset: turn stored gate metrics events into a tidy, metadata-only dataset and compute the KPIs in
docs/kpi/README.md.

Privacy by design: a row carries no developer identity (no login, no e-mail), no finding titles, no file paths and
no code. KPIs are meant for team / repository / week granularity, never for ranking individuals.

Deterministic: rows are sorted by (ts, run_id) and every aggregate is a pure function of the rows, so the same
events always produce byte-identical CSV / JSON.
"""
from __future__ import annotations

import csv
import io
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable

DATASET_VERSION = 1
SEVERITIES = ("blocker", "high", "medium", "low", "info")
# Categories that mean "a secret or a known-vulnerable component reached a commit". Non-waivable in the gate.
SECURITY_CRITICAL = ("secret-exposure", "hardcoded-credential", "known-vulnerable-dependency")
# Refs that do not identify a branch, so a fail -> pass sequence on them cannot be attributed to one piece of work.
_ANONYMOUS_REFS = {"", "HEAD"}
_UNKNOWN_REPO = "unknown/unknown"

# Column order of the CSV export (the contract for the Measurement tool; additive changes only).
COLUMNS = [
    "run_id", "ts", "week", "month", "repo", "ref", "event_name", "intent", "verdict", "blocked", "flagged",
    "threshold", "phases", "failed_phases", "files", "findings_total",
    *(f"findings_{s}" for s in SEVERITIES),
    "waived", "late", "unverified", "skip_requested", "skip_valid", "skip_phases", "skip_reason",
    "categories", "duration_s", "prompt_tokens", "completion_tokens",
    # Appended in dataset version 1 (additive): empty for events from engines that did not count lines yet.
    "lines_added", "lines_removed",
]

# One row per finding label a developer set with `ai-sdlc-gate triage` (see triage.py).
TRIAGE_COLUMNS = ["run_id", "ts", "week", "repo", "phase", "category", "severity", "label"]

# Time saved (K12) is an estimate. Every input that is not measured is named here and shown on the dashboard.
TIME_SAVED_ASSUMPTIONS = {
    # Fixing a blocking finding while the change is still open: the developer has the context, nothing to redeploy.
    "fix_hours_pre_merge": 0.5,
    # Fixing the same defect after merge: rediscovery, a new branch and review, possibly a redeploy. 5x the
    # pre-merge cost, the conservative end of the defect-cost escalation reported in the literature.
    "fix_hours_post_merge": 2.5,
    # Share of blocking findings that are real, used until enough findings are triaged to measure it.
    "assumed_precision": 0.8,
}
# Below this many labels the false-positive rate is reported as insufficient data (None).
MIN_TRIAGE_LABELS = 10


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _week(ts: datetime) -> str:
    y, w, _ = ts.isocalendar()
    return f"{y}-W{w:02d}"


def _categories(event: dict[str, Any]) -> dict[str, int]:
    """Category -> finding count. The brief (capped at 40 per run) gives counts; older events only list names."""
    brief = event.get("findings_brief") or []
    if brief:
        return dict(sorted(Counter(str(f.get("category") or "general") for f in brief).items()))
    return {str(c): 1 for c in sorted(event.get("top_categories") or [])}


def to_row(event: dict[str, Any]) -> dict[str, Any]:
    """One metadata-only row per gate run."""
    ts = _ts(event["ts"])
    counts = event.get("counts") or {}
    skip = event.get("skip") or {}
    usage = event.get("llm_usage") or {}
    phase_results = event.get("phase_results") or []
    return {
        "run_id": event["id"],
        "ts": ts.isoformat(timespec="seconds"),
        "week": _week(ts),
        "month": ts.strftime("%Y-%m"),
        "repo": str(event.get("repo") or _UNKNOWN_REPO),
        "ref": str(event.get("ref") or ""),
        "event_name": str(event.get("event_name") or ""),
        "intent": str(event.get("intent") or ""),
        "verdict": event["verdict"],
        "blocked": bool(event.get("blocked")),
        "flagged": bool(event.get("flagged")),
        "threshold": str(event.get("threshold") or ""),
        "phases": [int(p) for p in event.get("phases") or []],
        "failed_phases": sorted(int(p["phase"]) for p in phase_results if p.get("verdict") == "fail"),
        "files": int(event.get("files") or 0),
        "findings_total": int(event.get("findings_total") or 0),
        **{f"findings_{s}": int(counts.get(s) or 0) for s in SEVERITIES},
        "waived": int(event.get("waived_count") or 0),
        "late": int(event.get("late_count") or 0),
        "unverified": int(event.get("unverified_count") or 0),
        "skip_requested": bool(skip.get("requested")),
        "skip_valid": bool(skip.get("valid")),
        "skip_phases": [int(p) for p in skip.get("valid_phases") or []],
        "skip_reason": str(skip.get("reason") or "")[:200],
        "categories": _categories(event),
        "duration_s": float(event.get("duration_s") or 0.0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "lines_added": int(event["lines_added"]) if "lines_added" in event else None,
        "lines_removed": int(event["lines_removed"]) if "lines_removed" in event else None,
    }


def build_rows(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [to_row(e) for e in events]
    rows.sort(key=lambda r: (r["ts"], r["run_id"]))
    return rows


def build_triage_rows(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per finding label carried by an event (`triage`), with the carrying run's repository and week."""
    out = []
    for e in events:
        ts = _ts(e["ts"])
        for t in e.get("triage") or []:
            if t.get("label") not in ("accepted", "false-positive", "wont-fix"):
                continue
            out.append({
                "run_id": e["id"], "ts": ts.isoformat(timespec="seconds"), "week": _week(ts),
                "repo": str(e.get("repo") or _UNKNOWN_REPO), "phase": int(t.get("phase") or 0),
                "category": str(t.get("category") or "general"), "severity": str(t.get("severity") or "info"),
                "label": t["label"],
            })
    out.sort(key=lambda r: (r["ts"], r["run_id"], r["phase"], r["category"], r["label"]))
    return out


def triage_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=TRIAGE_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        out = dict(r)
        for k in ("phases", "failed_phases", "skip_phases"):
            out[k] = ";".join(str(p) for p in r[k])
        out["categories"] = ";".join(f"{c}:{n}" for c, n in r["categories"].items())
        for k in ("blocked", "flagged", "skip_requested", "skip_valid"):
            out[k] = "true" if r[k] else "false"
        w.writerow(out)
    return buf.getvalue()


# ----------------------------------------------------------------------------- KPIs

def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vs = sorted(values)
    if len(vs) == 1:
        return round(vs[0], 2)
    return round(statistics.quantiles(vs, n=100, method="inclusive")[int(q * 100) - 1], 2)


def _work_key(r: dict[str, Any]) -> tuple[str, str] | None:
    """The piece of work a run belongs to: (repo, branch). None when the run cannot be attributed."""
    if r["repo"] == _UNKNOWN_REPO or r["ref"] in _ANONYMOUS_REFS:
        return None
    return (r["repo"], r["ref"])


def time_to_green_hours(rows: list[dict[str, Any]]) -> list[float]:
    """Hours from the first failing run on a branch to the next passing run on it (one value per recovery)."""
    by_work: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = _work_key(r)
        if key is not None:
            by_work[key].append(r)
    out: list[float] = []
    for runs in by_work.values():
        failed_at: datetime | None = None
        for r in sorted(runs, key=lambda x: x["ts"]):
            if r["verdict"] == "fail" and failed_at is None:
                failed_at = _ts(r["ts"])
            elif r["verdict"] == "pass" and failed_at is not None:
                out.append(round((_ts(r["ts"]) - failed_at).total_seconds() / 3600, 3))
                failed_at = None
    return out


def first_time_right(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """(branches whose first gate run passed, branches with an attributable first run)."""
    first: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = _work_key(r)
        if key is not None and key not in first:
            first[key] = r
    return sum(1 for r in first.values() if r["verdict"] == "pass"), len(first)


def false_positive_rates(triage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """K13: share of labelled findings marked false positive, overall, per phase and per category.

    Labels are a sample: developers label what they dispute or confirm, not every finding, so the rate is reported
    only from MIN_TRIAGE_LABELS labels up (per group too) and always with its label count.
    """
    def rate(rs: list[dict[str, Any]]) -> float | None:
        return _rate(sum(1 for r in rs if r["label"] == "false-positive"), len(rs)) if len(rs) >= MIN_TRIAGE_LABELS else None

    by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in triage_rows:
        by_phase[str(r["phase"])].append(r)
        by_cat[r["category"]].append(r)
    return {
        "labels": len(triage_rows),
        "label_counts": dict(sorted(Counter(r["label"] for r in triage_rows).items())),
        "rate": rate(triage_rows),
        "by_phase": {p: {"labels": len(rs), "rate": rate(rs)} for p, rs in sorted(by_phase.items())},
        "by_category": {c: {"labels": len(rs), "rate": rate(rs)} for c, rs in sorted(by_cat.items())},
    }


def caught_blocking_findings(rows: list[dict[str, Any]]) -> int:
    """Blocking findings counted once per blocked streak on a branch.

    A finding stays in the report on every run until it is fixed, so summing findings over runs would count one
    defect several times. Each streak of failing runs on a branch counts the blocker + high findings of its first
    run only. Unattributable runs are left out, so this is a lower bound.
    """
    by_work: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = _work_key(r)
        if key is not None:
            by_work[key].append(r)
    caught = 0
    for runs in by_work.values():
        in_streak = False
        for r in sorted(runs, key=lambda x: x["ts"]):
            if r["verdict"] == "fail" and not in_streak:
                caught += r["findings_blocker"] + r["findings_high"]
                in_streak = True
            elif r["verdict"] == "pass":
                in_streak = False
    return caught


def time_saved(rows: list[dict[str, Any]], fp: dict[str, Any]) -> dict[str, Any]:
    """K12: estimated developer hours saved by catching blocking defects before merge, net of gate waiting time."""
    a = TIME_SAVED_ASSUMPTIONS
    caught = caught_blocking_findings(rows)
    measured = fp["rate"] is not None
    precision = round(1 - fp["rate"], 4) if measured else a["assumed_precision"]
    gross = caught * precision * (a["fix_hours_post_merge"] - a["fix_hours_pre_merge"])
    wait = sum(r["duration_s"] for r in rows) / 3600
    n = len(rows)
    return {
        "caught_blocking_findings": caught,
        "precision": precision,
        "precision_source": "measured from triage labels" if measured else "assumed",
        "gross_hours": round(gross, 1),
        "gate_wait_hours": round(wait, 1),
        "net_hours": round(gross - wait, 1),
        "net_hours_per_run": round((gross - wait) / n, 2) if n else None,
        "assumptions": dict(a),
    }


def compute_kpis(rows: list[dict[str, Any]], triage_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The KPIs of docs/kpi/README.md over `rows`. A value is None when the data cannot support it."""
    n = len(rows)
    passed = sum(1 for r in rows if r["verdict"] == "pass")
    blocked = sum(1 for r in rows if r["blocked"])
    blocking = sum(r["findings_blocker"] + r["findings_high"] for r in rows)
    ftr_ok, ftr_n = first_time_right(rows)
    phase_runs: Counter = Counter()
    phase_fails: Counter = Counter()
    for r in rows:
        phase_runs.update(r["phases"])
        phase_fails.update(r["failed_phases"])
    cats: Counter = Counter()
    for r in rows:
        cats.update(r["categories"])
    sec_runs = sum(1 for r in rows if any(c in r["categories"] for c in SECURITY_CRITICAL))
    findings_total = sum(r["findings_total"] for r in rows)
    ttg = time_to_green_hours(rows)
    durations = [r["duration_s"] for r in rows if r["duration_s"] > 0]
    metered = [r for r in rows if r["prompt_tokens"] or r["completion_tokens"]]
    sized = [r for r in rows if r["lines_added"] is not None]
    changed = sum(r["lines_added"] + r["lines_removed"] for r in sized)
    fp = false_positive_rates(triage_rows or [])
    return {
        "runs": n,
        "gate_pass_rate": _rate(passed, n),
        "first_time_right_rate": _rate(ftr_ok, ftr_n),
        "first_time_right_branches": ftr_n,
        "block_rate": _rate(blocked, n),
        "blocking_findings_per_run": round(blocking / n, 3) if n else None,
        # Only runs whose event reports changed lines (engines from this release on) count, on both sides.
        "blocking_findings_per_kloc": round(sum(r["findings_blocker"] + r["findings_high"] for r in sized) / changed * 1000, 2) if changed else None,
        "sized_run_share": _rate(len(sized), n),
        "phase_fail_rate": {str(p): _rate(phase_fails[p], phase_runs[p]) for p in sorted(phase_runs)},
        "security_critical_run_rate": _rate(sec_runs, n),
        "top_categories": dict(cats.most_common(8)),
        "time_to_green_hours_median": _quantile(ttg, 0.5),
        "time_to_green_recoveries": len(ttg),
        "skip_request_rate": _rate(sum(1 for r in rows if r["skip_requested"]), n),
        "skip_granted_rate": _rate(sum(1 for r in rows if r["skip_valid"]), n),
        "waived_findings": sum(r["waived"] for r in rows),
        "unverified_finding_share": _rate(sum(r["unverified"] for r in rows), findings_total),
        "gate_latency_s_p50": _quantile(durations, 0.5),
        "gate_latency_s_p90": _quantile(durations, 0.9),
        "tokens_per_run": round(sum(r["prompt_tokens"] + r["completion_tokens"] for r in metered) / len(metered)) if metered else None,
        "token_metered_share": _rate(len(metered), n),
        "attributable_share": _rate(sum(1 for r in rows if _work_key(r) is not None), n),
        "time_saved": time_saved(rows, fp),
        "false_positives": fp,
    }


def kpi_summary(rows: list[dict[str, Any]], triage_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Overall, per-week and per-repository KPIs: the payload the dashboard renders."""
    triage_rows = triage_rows or []
    weeks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    repos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    t_weeks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    t_repos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        weeks[r["week"]].append(r)
        repos[r["repo"]].append(r)
    for t in triage_rows:
        t_weeks[t["week"]].append(t)
        t_repos[t["repo"]].append(t)
    return {
        "dataset_version": DATASET_VERSION,
        "period": {"from": rows[0]["ts"] if rows else None, "to": rows[-1]["ts"] if rows else None},
        "overall": compute_kpis(rows, triage_rows),
        "weeks": {w: compute_kpis(rs, t_weeks.get(w)) for w, rs in sorted(weeks.items())},
        "repos": {k: compute_kpis(rs, t_repos.get(k)) for k, rs in sorted(repos.items())},
        "skip_reasons": [
            {"ts": r["ts"], "repo": r["repo"], "phases": r["skip_phases"], "reason": r["skip_reason"]}
            for r in rows if r["skip_requested"]
        ],
        "min_triage_labels": MIN_TRIAGE_LABELS,
    }


def export(events: Iterable[dict[str, Any]]) -> dict[str, str]:
    """All export artefacts as {file name: content}. Pure function of the events."""
    from .kpi_dashboard import render_dashboard

    events = list(events)
    rows = build_rows(events)
    triage_rows = build_triage_rows(events)
    summary = kpi_summary(rows, triage_rows)
    return {
        "kpi-runs.csv": rows_to_csv(rows),
        "kpi-runs.json": json.dumps({"dataset_version": DATASET_VERSION, "columns": COLUMNS, "rows": rows}, indent=1, sort_keys=True) + "\n",
        "kpi-triage.csv": triage_to_csv(triage_rows),
        "kpi-summary.json": json.dumps(summary, indent=1, sort_keys=True) + "\n",
        "kpi-dashboard.html": render_dashboard(summary, rows),
    }
