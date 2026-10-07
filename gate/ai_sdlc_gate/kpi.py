"""KPI dataset: turn the gate's measured data streams into a tidy, metadata-only dataset and compute the KPIs in
docs/kpi/README.md.

Measured only. Every number is counted or timed from a data stream: gate run events, finding labels developers set,
git history of the gated repositories and GitHub pull requests. Nothing is estimated from assumed parameters;
a KPI without data is reported as None ("no data yet") together with what would collect it.

Privacy by design: a row carries no developer identity (no login, no e-mail), no finding titles, no file paths and
no code. KPIs are for team / repository / period granularity, never for ranking individuals; any count of people
below MIN_GROUP is suppressed.

Deterministic: rows are sorted and every aggregate is a pure function of the inputs, so the same inputs always
produce byte-identical CSV / JSON.
"""
from __future__ import annotations

import csv
import fnmatch
import hashlib
import hmac
import io
import json
import secrets
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Iterable

from .kpi_sources import person_key, subkey

# Covers kpi-runs.*, kpi-summary.json and kpi-portal.json. Adding keys keeps the version; removing, renaming or
# changing the meaning of a key bumps it. 2: summary `feedback` replaced `false_positives`, `time_saved` removed
# (PR #36, which should have bumped it), portal export added.
DATASET_VERSION = 2
SEVERITIES = ("blocker", "high", "medium", "low", "info")
# Categories that mean "a secret or a known-vulnerable component reached a commit". Non-waivable in the gate.
SECURITY_CRITICAL = ("secret-exposure", "hardcoded-credential", "known-vulnerable-dependency")
# Refs that do not identify a branch, so a fail -> pass sequence on them cannot be attributed to one piece of work.
_ANONYMOUS_REFS = {"", "HEAD"}
_UNKNOWN_REPO = "unknown/unknown"
UNATTRIBUTED_TEAM = "(unattributed)"

# Column order of the CSV export (the contract for the Measurement tool; additive changes only).
COLUMNS = [
    "run_id", "ts", "week", "month", "repo", "ref", "event_name", "intent", "verdict", "blocked", "flagged",
    "threshold", "phases", "failed_phases", "files", "findings_total",
    *(f"findings_{s}" for s in SEVERITIES),
    "waived", "late", "unverified", "skip_requested", "skip_valid", "skip_phases", "skip_reason",
    "categories", "duration_s", "prompt_tokens", "completion_tokens",
    # Appended in dataset version 1 (additive): empty for events from engines that did not count lines yet.
    "lines_added", "lines_removed",
    "team",
]

# One row per finding label a developer set with `ai-sdlc-gate triage` (see triage.py).
TRIAGE_COLUMNS = ["run_id", "ts", "week", "repo", "phase", "category", "severity", "label"]

# Below this many labels a feedback / false-positive rate is reported as insufficient data (None).
MIN_TRIAGE_LABELS = 10
# Counts of people (gate users, committers) below this are suppressed: works-council rule, no small-group exposure.
MIN_GROUP = 5

# Adoption phases, defined once for every team (not tuned per team). A week is "active" for a team with at least
# ACTIVE_WEEK_RUNS gate runs. The phase in a week follows the run of consecutive active weeks ending there.
ACTIVE_WEEK_RUNS = 5
REGULAR_STREAK = 2       # 2 consecutive active weeks  -> regular
OPERATIONAL_STREAK = 4   # 4 consecutive active weeks  -> operational; anything less with runs -> experimental


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _week(ts: datetime) -> str:
    y, w, _ = ts.isocalendar()
    return f"{y}-W{w:02d}"


def _week_index(week: str) -> int:
    y, w = week.split("-W")
    return datetime.fromisocalendar(int(y), int(w), 1).toordinal() // 7


# ----------------------------------------------------------------------------- teams

def team_of(repo: str, teams: dict[str, list[str]] | None = None) -> str:
    """The team a repository belongs to: the first matching glob of the team map, else its GitHub owner.

    The owner fallback is measured (it is part of the slug) but coarse; a team map (`--teams`, see the README)
    makes it exact. Runs without a known repository are `(unattributed)`.
    """
    if not repo or repo == _UNKNOWN_REPO:
        return UNATTRIBUTED_TEAM
    for team, globs in sorted((teams or {}).items()):
        if any(fnmatch.fnmatchcase(repo.lower(), g.lower()) for g in globs):
            return team
    return repo.split("/", 1)[0]


# ----------------------------------------------------------------------------- the run dataset

def _categories(event: dict[str, Any]) -> dict[str, int]:
    """Category -> finding count. The brief (capped at 40 per run) gives counts; older events only list names."""
    brief = event.get("findings_brief") or []
    if brief:
        return dict(sorted(Counter(str(f.get("category") or "general") for f in brief).items()))
    return {str(c): 1 for c in sorted(event.get("top_categories") or [])}


def to_row(event: dict[str, Any], teams: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """One metadata-only row per gate run."""
    ts = _ts(event["ts"])
    counts = event.get("counts") or {}
    skip = event.get("skip") or {}
    usage = event.get("llm_usage") or {}
    phase_results = event.get("phase_results") or []
    repo = str(event.get("repo") or _UNKNOWN_REPO)
    return {
        "run_id": event["id"],
        "ts": ts.isoformat(timespec="seconds"),
        "week": _week(ts),
        "month": ts.strftime("%Y-%m"),
        "repo": repo,
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
        "team": team_of(repo, teams),
    }


def build_rows(events: Iterable[dict[str, Any]], teams: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    rows = [to_row(e, teams) for e in events]
    rows.sort(key=lambda r: (r["ts"], r["run_id"]))
    return rows


def gate_users(events: Iterable[dict[str, Any]], teams: dict[str, list[str]] | None, salt: str) -> list[tuple[str, str, str]]:
    """(team, month, person key) per run with a verified developer: used only for suppressed distinct counts.

    Kept in memory and apart from the exported rows on purpose: no export carries a per-person key.
    """
    out = []
    for e in events:
        email = str(e.get("developer_email") or "").strip().lower()
        if email:
            out.append((team_of(str(e.get("repo") or _UNKNOWN_REPO), teams), _ts(e["ts"]).strftime("%Y-%m"), person_key(email, salt)))
    return out


def validate_teams(teams: dict[str, list[str]], repos: Iterable[str]) -> list[str]:
    """Problems in a team map against the repositories in the data: unusable globs, overlaps, unused teams.

    Overlaps are resolved deterministically (the first team in name order wins), but they are reported so the map
    can be made exact.
    """
    problems = []
    for team, globs in sorted(teams.items()):
        for g in globs:
            if "/" not in g:
                problems.append(f"team {team!r}: glob {g!r} has no owner/ part, so it can match no repository slug")
    repos = sorted(set(repos))
    for repo in repos:
        hits = [t for t, globs in sorted(teams.items()) if any(fnmatch.fnmatchcase(repo.lower(), g.lower()) for g in globs)]
        if len(hits) > 1:
            problems.append(f"repository {repo!r} matches teams {hits}; it is counted for {hits[0]!r}")
    for team, globs in sorted(teams.items()):
        if not any(any(fnmatch.fnmatchcase(r.lower(), g.lower()) for g in globs) for r in repos):
            problems.append(f"team {team!r} matches no repository in the data")
    return problems


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


def _csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def triage_to_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(rows, TRIAGE_COLUMNS)


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    flat = []
    for r in rows:
        out = dict(r)
        for k in ("phases", "failed_phases", "skip_phases"):
            out[k] = ";".join(str(p) for p in r[k])
        out["categories"] = ";".join(f"{c}:{n}" for c, n in r["categories"].items())
        for k in ("blocked", "flagged", "skip_requested", "skip_valid"):
            out[k] = "true" if r[k] else "false"
        flat.append(out)
    return _csv(flat, COLUMNS)


# ----------------------------------------------------------------------------- helpers

def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vs = sorted(values)
    if len(vs) == 1:
        return round(vs[0], 2)
    return round(statistics.quantiles(vs, n=100, method="inclusive")[int(q * 100) - 1], 2)


def _suppressed(n: int) -> int | None:
    """A count of people, or None when the group is too small to show (MIN_GROUP)."""
    return n if n >= MIN_GROUP else None


def _work_key(r: dict[str, Any]) -> tuple[str, str] | None:
    """The piece of work a run belongs to: (repo, branch). None when the run cannot be attributed."""
    if r["repo"] == _UNKNOWN_REPO or r["ref"] in _ANONYMOUS_REFS:
        return None
    return (r["repo"], r["ref"])


# ----------------------------------------------------------------------------- blocks and fix cycles

def block_streaks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each streak of failing runs on a branch: its first run's blocking findings, length and how it ended.

    A finding stays in the report on every run until it is fixed, so a streak counts the blocker + high findings
    of its first run only. `resolved_after_h` is the measured time to the next passing run on the branch (None if
    the branch has not turned green yet). Unattributable runs are left out.
    """
    by_work: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = _work_key(r)
        if key is not None:
            by_work[key].append(r)
    streaks: list[dict[str, Any]] = []
    for key, runs in sorted(by_work.items()):
        current: dict[str, Any] | None = None
        for r in sorted(runs, key=lambda x: x["ts"]):
            if r["verdict"] == "fail":
                if current is None:
                    current = {"repo": key[0], "team": r["team"], "start": r["ts"], "failing_runs": 0,
                               "blocking_findings": r["findings_blocker"] + r["findings_high"], "resolved_after_h": None}
                current["failing_runs"] += 1
            elif r["verdict"] == "pass" and current is not None:
                current["resolved_after_h"] = round((_ts(r["ts"]) - _ts(current["start"])).total_seconds() / 3600, 3)
                streaks.append(current)
                current = None
        if current is not None:
            streaks.append(current)
    return streaks


def time_to_green_hours(rows: list[dict[str, Any]]) -> list[float]:
    """Hours from the first failing run on a branch to the next passing run on it (one value per recovery)."""
    return [s["resolved_after_h"] for s in block_streaks(rows) if s["resolved_after_h"] is not None]


def first_time_right(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """(branches whose first gate run passed, branches with an attributable first run)."""
    first: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = _work_key(r)
        if key is not None and key not in first:
            first[key] = r
    return sum(1 for r in first.values() if r["verdict"] == "pass"), len(first)


# ----------------------------------------------------------------------------- feedback

def feedback(triage_rows: list[dict[str, Any]], findings_in_scope: int) -> dict[str, Any]:
    """Developer feedback on findings: positive share, false-positive rate and how many findings were labelled.

    `accepted` is positive feedback, `false-positive` negative; `wont-fix` confirms the finding but declines it,
    so it counts towards coverage and the false-positive rate but not towards positive feedback. Rates are shown
    only from MIN_TRIAGE_LABELS labels up (per group too), always with the label count.
    """
    def fp_rate(rs: list[dict[str, Any]]) -> float | None:
        return _rate(sum(1 for r in rs if r["label"] == "false-positive"), len(rs)) if len(rs) >= MIN_TRIAGE_LABELS else None

    by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in triage_rows:
        by_phase[str(r["phase"])].append(r)
        by_cat[r["category"]].append(r)
    counts = Counter(r["label"] for r in triage_rows)
    rated = counts["accepted"] + counts["false-positive"]
    return {
        "labels": len(triage_rows),
        "label_counts": dict(sorted(counts.items())),
        "label_coverage": _rate(len(triage_rows), findings_in_scope),
        "positive_share": _rate(counts["accepted"], rated) if rated >= MIN_TRIAGE_LABELS else None,
        "rate": fp_rate(triage_rows),
        "by_phase": {p: {"labels": len(rs), "rate": fp_rate(rs)} for p, rs in sorted(by_phase.items())},
        "by_category": {c: {"labels": len(rs), "rate": fp_rate(rs)} for c, rs in sorted(by_cat.items())},
    }


# Kept for callers of the previous name.
def false_positive_rates(triage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return feedback(triage_rows, 0)


# ----------------------------------------------------------------------------- per-scope KPIs

def compute_kpis(rows: list[dict[str, Any]], triage_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The run-based KPIs of docs/kpi/README.md over `rows`. A value is None when the data cannot support it."""
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
    streaks = block_streaks(rows)
    resolved = [s for s in streaks if s["resolved_after_h"] is not None]
    durations = [r["duration_s"] for r in rows if r["duration_s"] > 0]
    metered = [r for r in rows if r["prompt_tokens"] or r["completion_tokens"]]
    tokens = [r["prompt_tokens"] + r["completion_tokens"] for r in metered]
    sized = [r for r in rows if r["lines_added"] is not None]
    changed = sum(r["lines_added"] + r["lines_removed"] for r in sized)
    return {
        "runs": n,
        "active_repos": len({r["repo"] for r in rows if r["repo"] != _UNKNOWN_REPO}),
        "gate_pass_rate": _rate(passed, n),
        "first_time_right_rate": _rate(ftr_ok, ftr_n),
        "first_time_right_branches": ftr_n,
        "block_rate": _rate(blocked, n),
        "blocking_findings_per_run": round(blocking / n, 3) if n else None,
        # Only runs whose event reports changed lines (engines from PR #34 on) count, on both sides.
        "blocking_findings_per_kloc": round(sum(r["findings_blocker"] + r["findings_high"] for r in sized) / changed * 1000, 2) if changed else None,
        "sized_run_share": _rate(len(sized), n),
        "phase_fail_rate": {str(p): _rate(phase_fails[p], phase_runs[p]) for p in sorted(phase_runs)},
        "security_critical_run_rate": _rate(sec_runs, n),
        "top_categories": dict(cats.most_common(8)),
        # Caught and resolved before merge: blocks on a branch that a later passing run on that branch cleared.
        "blocks": len(streaks),
        "blocks_resolved": len(resolved),
        "blocking_findings_resolved": sum(s["blocking_findings"] for s in resolved),
        "time_to_green_hours_median": _quantile([s["resolved_after_h"] for s in resolved], 0.5),
        "time_to_green_recoveries": len(resolved),
        "fix_iterations_median": _quantile([float(s["failing_runs"]) for s in resolved], 0.5),
        "skip_request_rate": _rate(sum(1 for r in rows if r["skip_requested"]), n),
        "skip_granted_rate": _rate(sum(1 for r in rows if r["skip_valid"]), n),
        "waived_findings": sum(r["waived"] for r in rows),
        "unverified_finding_share": _rate(sum(r["unverified"] for r in rows), findings_total),
        "gate_latency_s_p50": _quantile(durations, 0.5),
        "gate_latency_s_p90": _quantile(durations, 0.9),
        "tokens_per_run": round(sum(tokens) / len(tokens)) if tokens else None,
        "tokens_p50": _quantile([float(t) for t in tokens], 0.5),
        "tokens_p90": _quantile([float(t) for t in tokens], 0.9),
        "tokens_total": sum(tokens),
        "token_metered_share": _rate(len(metered), n),
        "attributable_share": _rate(sum(1 for r in rows if _work_key(r) is not None), n),
        "feedback": feedback(triage_rows or [], findings_total),
    }


# ----------------------------------------------------------------------------- adoption

def adoption(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per team: runs per ISO week from its first run to the last week in the data, with the measured phase."""
    weeks_all = sorted({r["week"] for r in rows})
    if not weeks_all:
        return {}
    last = _week_index(weeks_all[-1])
    out: dict[str, Any] = {}
    by_team: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_team[r["team"]][r["week"]] += 1
    for team, counts in sorted(by_team.items()):
        first = min(_week_index(w) for w in counts)
        index_to_week = {_week_index(w): w for w in weeks_all}
        series = []
        streak = 0
        for i in range(first, last + 1):
            # Mondays have ordinals 7k + 1 (date(1, 1, 1) is a Monday), so week index k starts on ordinal 7k + 1.
            week = index_to_week.get(i) or datetime.fromordinal(i * 7 + 1).strftime("%G-W%V")
            runs = counts.get(week, 0)
            streak = streak + 1 if runs >= ACTIVE_WEEK_RUNS else 0
            phase = "operational" if streak >= OPERATIONAL_STREAK else "regular" if streak >= REGULAR_STREAK else "experimental"
            series.append({"week": week, "runs": runs, "phase": phase})
        out[team] = {"first_run": min(r["ts"] for r in rows if r["team"] == team)[:10], "weeks": series,
                     "phase": series[-1]["phase"]}
    return out


def cases_by_month(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        out[r["month"]][r["team"]] += 1
    return {m: dict(sorted(c.items())) for m, c in sorted(out.items())}


def users(gate_user_rows: list[tuple[str, str, str]], git_rows: list[dict[str, Any]], teams: dict[str, list[str]] | None,
          gated_repos: set[str], label: Callable[[str], str] = lambda t: t) -> dict[str, Any]:
    """Distinct gate users and, where git history is available, committers in the same teams' gated repositories.

    Every count below MIN_GROUP is suppressed (None). Coverage compares two people sets keyed the same way; it is
    only reported when both are shown. The gate keys people by their verified sign-in e-mail and git by the commit
    e-mail; when developers commit with another address, coverage reads low, never high.
    """
    gate_by_team: dict[str, set[str]] = defaultdict(set)
    for team, _, key in gate_user_rows:
        gate_by_team[team].add(key)
    git_by_team: dict[str, set[str]] = defaultdict(set)
    for g in git_rows:
        if g["repo"] in gated_repos and not g.get("merge"):
            git_by_team[label(team_of(g["repo"], teams))].add(g["author"])
    out = {}
    for team in sorted(set(gate_by_team) | set(git_by_team)):
        u, c = _suppressed(len(gate_by_team[team])), _suppressed(len(git_by_team[team]))
        out[team] = {"gate_users": u, "committers": c,
                     "coverage": _rate(len(gate_by_team[team] & git_by_team[team]), len(git_by_team[team])) if u and c else None}
    all_gate = {k for _, _, k in gate_user_rows}
    out_total = _suppressed(len(all_gate))
    return {"total_gate_users": out_total, "by_team": out}


# ----------------------------------------------------------------------------- outcomes from git and PRs

def _adoption_dates(rows: list[dict[str, Any]]) -> dict[str, str]:
    first: dict[str, str] = {}
    for r in rows:
        if r["repo"] != _UNKNOWN_REPO and (r["repo"] not in first or r["ts"] < first[r["repo"]]):
            first[r["repo"]] = r["ts"]
    return first


def _cohort(repo: str, ts: str, adopted: dict[str, str]) -> str:
    if repo not in adopted:
        return "ungated"
    return "gated_after" if _ts(ts) >= _ts(adopted[repo]) else "gated_before"


def quality_outcome(git_rows: list[dict[str, Any]], adopted: dict[str, str]) -> dict[str, Any] | None:
    """Revert and fix-commit rates of non-merge commits: gated repos before / after their first gate run, and
    repositories never gated. None without git history."""
    if not git_rows:
        return None
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in git_rows:
        if not g.get("merge"):
            groups[_cohort(g["repo"], g["ts"], adopted)].append(g)
    return {
        c: {"commits": len(gs), "repos": len({g["repo"] for g in gs}),
            "revert_rate": _rate(sum(1 for g in gs if g["revert"]), len(gs)),
            "fix_commit_rate": _rate(sum(1 for g in gs if g["fix"]), len(gs))}
        for c, gs in sorted(groups.items())
    }


def review_effect(pr_rows: list[dict[str, Any]], adopted: dict[str, str]) -> dict[str, Any] | None:
    """Merged pull requests: cycle time (opened -> merged), review rounds and review comments, per cohort.
    None without PR data."""
    merged = [p for p in pr_rows if p.get("merged_at")]
    if not merged:
        return None
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in merged:
        groups[_cohort(p["repo"], p["merged_at"], adopted)].append(p)
    out = {}
    for c, ps in sorted(groups.items()):
        cycle = [(_ts(p["merged_at"]) - _ts(p["created_at"])).total_seconds() / 3600 for p in ps]
        out[c] = {
            "prs": len(ps), "repos": len({p["repo"] for p in ps}),
            "cycle_hours_median": _quantile(cycle, 0.5),
            "reviews_median": _quantile([float(p["reviews"]) for p in ps if p.get("reviews") is not None], 0.5),
            "changes_requested_share": _rate(sum(1 for p in ps if (p.get("changes_requested") or 0) > 0), len(ps)),
            "review_comments_median": _quantile([float(p["review_comments"]) for p in ps if p.get("review_comments") is not None], 0.5),
            "revert_pr_rate": _rate(sum(1 for p in ps if p.get("revert")), len(ps)),
        }
    return out


# ----------------------------------------------------------------------------- summary and export

def kpi_summary(rows: list[dict[str, Any]], triage_rows: list[dict[str, Any]] | None = None, *,
                gate_user_rows: list[tuple[str, str, str]] | None = None, git_rows: list[dict[str, Any]] | None = None,
                pr_rows: list[dict[str, Any]] | None = None, teams: dict[str, list[str]] | None = None,
                label: Callable[[str], str] = lambda t: t) -> dict[str, Any]:
    """Every KPI: overall, per ISO week, per repository and per team, plus adoption and outcome comparisons."""
    triage_rows = triage_rows or []
    git_rows = git_rows or []
    pr_rows = pr_rows or []
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {"week": defaultdict(list), "repo": defaultdict(list), "team": defaultdict(list)}
    tgroups: dict[str, dict[str, list[dict[str, Any]]]] = {"week": defaultdict(list), "repo": defaultdict(list), "team": defaultdict(list)}
    for r in rows:
        for g in groups:
            groups[g][r[g]].append(r)
    for t in triage_rows:
        tgroups["week"][t["week"]].append(t)
        tgroups["repo"][t["repo"]].append(t)
        tgroups["team"][label(team_of(t["repo"], teams))].append(t)
    adopted = _adoption_dates(rows)
    return {
        "dataset_version": DATASET_VERSION,
        "period": {"from": rows[0]["ts"] if rows else None, "to": rows[-1]["ts"] if rows else None},
        "overall": compute_kpis(rows, triage_rows),
        "weeks": {k: compute_kpis(v, tgroups["week"].get(k)) for k, v in sorted(groups["week"].items())},
        "repos": {k: compute_kpis(v, tgroups["repo"].get(k)) for k, v in sorted(groups["repo"].items())},
        "teams": {k: compute_kpis(v, tgroups["team"].get(k)) for k, v in sorted(groups["team"].items())},
        "adoption": adoption(rows),
        "cases_by_month": cases_by_month(rows),
        "users": users(gate_user_rows or [], git_rows, teams, set(adopted), label),
        "quality_outcome": quality_outcome(git_rows, adopted),
        "review_effect": review_effect(pr_rows, adopted),
        "sources": {"gate_runs": len(rows), "triage_labels": len(triage_rows), "git_commits": len(git_rows),
                    "git_repos": len({g["repo"] for g in git_rows}), "pull_requests": len(pr_rows),
                    "pr_repos": len({p["repo"] for p in pr_rows}), "team_map": bool(teams)},
        "skip_reasons": [
            {"ts": r["ts"], "repo": r["repo"], "phases": r["skip_phases"], "reason": r["skip_reason"]}
            for r in rows if r["skip_requested"]
        ],
        "rules": {"min_triage_labels": MIN_TRIAGE_LABELS, "min_group": MIN_GROUP, "active_week_runs": ACTIVE_WEEK_RUNS,
                  "regular_streak_weeks": REGULAR_STREAK, "operational_streak_weeks": OPERATIONAL_STREAK},
    }


def export(events: Iterable[dict[str, Any]], *, git_rows: list[dict[str, Any]] | None = None,
           pr_rows: list[dict[str, Any]] | None = None, teams: dict[str, list[str]] | None = None,
           salt: str | None = None) -> dict[str, str]:
    """All export artefacts as {file name: content}. Pure function of the inputs.

    `salt` must be the key `kpi collect-git` used, for committer coverage to match people across git and the gate.
    Without one, a random key keeps the distinct counts right but makes coverage meaningless (it is then None,
    because no git person key can match).
    """
    from .kpi_dashboard import render_dashboard

    events = list(events)
    rows = build_rows(events, teams)
    triage_rows = build_triage_rows(events)
    summary = kpi_summary(rows, triage_rows, gate_user_rows=gate_users(events, teams, salt or secrets.token_hex(16)),
                          git_rows=git_rows, pr_rows=pr_rows, teams=teams)
    return {
        "kpi-runs.csv": rows_to_csv(rows),
        "kpi-runs.json": json.dumps({"dataset_version": DATASET_VERSION, "columns": COLUMNS, "rows": rows}, indent=1, sort_keys=True) + "\n",
        "kpi-triage.csv": triage_to_csv(triage_rows),
        "kpi-summary.json": json.dumps(summary, indent=1, sort_keys=True) + "\n",
        "kpi-dashboard.html": render_dashboard(summary),
    }


# ----------------------------------------------------------------------------- portal export

PORTAL_SCHEMA = "ai-sdlc-gate/kpi-portal"
OTHER_TEAMS = "Other teams"


def team_label(team: str, salt: str, real: bool = False) -> str:
    """The name a team is shown under outside the gate: a stable pseudonym unless real names were approved.

    Keyed with the machine's secret, so the label of a team never changes when another team appears (an
    alphabetical "Team A, B, ..." would relabel teams between refreshes) and cannot be reversed by guessing names.
    """
    if real:
        return team
    return "Team " + hmac.new(subkey(salt, "team-labels"), team.encode("utf-8"), hashlib.sha256).hexdigest()[:6]


def portal_export(events: Iterable[dict[str, Any]], *, salt: str, git_rows: list[dict[str, Any]] | None = None,
                  pr_rows: list[dict[str, Any]] | None = None, teams: dict[str, list[str]] | None = None,
                  real_team_names: bool = False) -> dict[str, Any]:
    """The sanitised dataset for publishing outside the gate (e.g. the AI Innovation Portal).

    - Only aggregate sections; no repository names, skip reasons, run rows, finding text or person keys.
    - A team is shown on its own only with at least MIN_GROUP verified gate users; smaller teams (and runs without
      a known repository) are folded into "Other teams", recomputed from the run rows (rates and medians cannot be
      combined from per-team summaries). If "Other teams" itself has fewer than MIN_GROUP users it is left out of
      every per-team section, so it cannot expose a small team under another name; the organisation-wide numbers
      still include its runs.
    - Team labels are stable pseudonyms unless `real_team_names` (needs the data owner's approval).
    """
    if not salt:  # fail before any data is processed: without the secret there are no stable pseudonyms
        raise ValueError("a salt is required for the portal export")
    events = list(events)
    git_rows, pr_rows = git_rows or [], pr_rows or []
    rows = build_rows(events, teams)
    user_rows = gate_users(events, teams, salt)
    people: dict[str, set[str]] = defaultdict(set)
    for team, _, key in user_rows:
        people[team].add(key)
    shown = {t for t, keys in people.items() if len(keys) >= MIN_GROUP and t != UNATTRIBUTED_TEAM}

    def label(team: str) -> str:
        return team_label(team, salt, real_team_names) if team in shown else OTHER_TEAMS

    folded = {r["team"] for r in rows} - shown
    other_users = len(set().union(*(people[t] for t in folded))) if folded else 0
    other_shown = bool(folded) and other_users >= MIN_GROUP
    summary = kpi_summary(
        [{**r, "team": label(r["team"])} for r in rows], build_triage_rows(events),
        gate_user_rows=[(label(t), m, k) for t, m, k in user_rows], git_rows=git_rows, pr_rows=pr_rows,
        teams=teams, label=label,
    )

    def strip(k: dict[str, Any]) -> dict[str, Any]:
        return {key: v for key, v in k.items() if key != "top_categories"}

    def per_team(d: dict[str, Any]) -> dict[str, Any]:
        return {t: v for t, v in d.items() if t != OTHER_TEAMS or other_shown}

    def outcome(section: dict[str, Any] | None, repos: int, people: int | None) -> dict[str, Any] | None:
        if section is None:
            return None
        # A comparison is a pilot, not a picture of the organisation, when it rests on fewer than MIN_GROUP
        # repositories or (where people are known) fewer than MIN_GROUP distinct committers: five repositories of
        # one maintainer are still one person's history.
        small = repos < MIN_GROUP or (people is not None and people < MIN_GROUP)
        return {"scope": "pilot" if small else "organisation", "repositories": repos, "cohorts": section}

    src = summary["sources"]
    committers = len({g["author"] for g in git_rows if not g.get("merge")})
    return {
        "schema": PORTAL_SCHEMA,
        "dataset_version": DATASET_VERSION,
        "period": summary["period"],
        "overall": strip(summary["overall"]),
        "teams": {t: strip(v) for t, v in per_team(summary["teams"]).items()},
        "weeks": {w: strip(v) for w, v in summary["weeks"].items()},
        "adoption": per_team(summary["adoption"]),
        "cases_by_month": {m: per_team(c) for m, c in summary["cases_by_month"].items()},
        "users": {"total_gate_users": summary["users"]["total_gate_users"], "by_team": per_team(summary["users"]["by_team"])},
        "quality_outcome": outcome(summary["quality_outcome"], src["git_repos"], committers),
        # Pull request rows carry no author, so only the repository count applies here.
        "review_effect": outcome(summary["review_effect"], src["pr_repos"], None),
        "sources": src,
        "rules": summary["rules"],
        "suppression": {
            "min_group": MIN_GROUP,
            "teams_shown": len(shown),
            "teams_folded": len(folded),
            "other_teams_shown": other_shown,
            "labels": "real" if real_team_names else "pseudonymous",
            # True when even the whole organisation has fewer than MIN_GROUP verified users.
            "organisation_below_min_group": summary["users"]["total_gate_users"] is None,
        },
    }
