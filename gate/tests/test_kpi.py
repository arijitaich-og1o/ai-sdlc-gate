"""KPI exporter and dashboard: metadata only, deterministic, formulas as documented in docs/kpi/README.md."""
from __future__ import annotations

import csv
import io
import json
import random
import re
import uuid

import pytest

from ai_sdlc_gate import kpi
from ai_sdlc_gate.kpi_dashboard import render_dashboard
from ai_sdlc_gate.metrics import ingest_event, validate_event

_NS = uuid.UUID("6f1c0a52-1d8e-4f43-9a3b-2b8f0c6d7e11")


def ev(n: int, ts: str, verdict: str = "pass", repo: str = "org/app", ref: str = "feature/x", **kw) -> dict:
    """A schema-1 metrics event as build_event writes it (only the fields the KPIs read are varied)."""
    counts = {"blocker": 0, "high": 0, "medium": 0, "low": 0, "info": 0, **kw.pop("counts", {})}
    failed = kw.pop("failed_phases", [])
    phases = kw.pop("phases", [3, 4, 5, 8])
    e = {
        "schema": 1,
        "id": str(uuid.uuid5(_NS, str(n))),
        "ts": ts,
        "repo": repo,
        "actor": "dev-one",
        "author_email": "dev.one@example.com",
        "developer_email": "dev.one@example.com",
        "email_verified": True,
        "client_attested": True,
        "ref": ref,
        "sha": f"{n:040x}",
        "event_name": "local-commit",
        "intent": "commit",
        "intent_source": "default",
        "phases": phases,
        "verdict": verdict,
        "flagged": verdict == "fail",
        "blocked": verdict == "fail",
        "threshold": "high",
        "counts": counts,
        "waived_count": 0,
        "late_count": 0,
        "unverified_count": 0,
        "findings_total": sum(counts.values()),
        "skip": {"requested": False, "valid": False, "requested_phases": [], "valid_phases": [], "reason": "", "errors": []},
        "phase_results": [{"phase": p, "verdict": "fail" if p in failed else "pass", "counts": {}, "skill_version": "1.0.0", "error": False} for p in phases],
        "top_categories": [],
        "findings_brief": [],
        "files": 3,
        "llm_usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        "duration_s": 30.0,
    }
    e.update(kw)
    assert not validate_event(e), validate_event(e)
    return e


def brief(*cats: str) -> list[dict]:
    return [{"phase": 8, "severity": "high", "category": c, "title": "Secret `AKIA...` in config.py", "file": "src/config.py", "waived": False} for c in cats]


# ----------------------------------------------------------------------------- the dataset

def test_rows_carry_metadata_only():
    e = ev(1, "2026-10-01T10:00:00+00:00", "fail", counts={"high": 1}, failed_phases=[8],
           findings_brief=brief("hardcoded-credential"), top_categories=["hardcoded-credential"])
    files = kpi.export([e])
    for name in ("kpi-runs.csv", "kpi-runs.json", "kpi-summary.json", "kpi-dashboard.html"):
        text = files[name]
        for leaked in ("dev.one@example.com", "dev-one", "AKIA", "src/config.py", "Secret `", e["sha"]):
            assert leaked not in text, f"{leaked!r} leaked into {name}"
    row = kpi.build_rows([e])[0]
    assert row["categories"] == {"hardcoded-credential": 1} and row["failed_phases"] == [8]


def test_export_is_deterministic_and_order_independent():
    events = [ev(i, f"2026-10-0{1 + i % 5}T1{i % 10}:00:00+00:00", "fail" if i % 3 == 0 else "pass") for i in range(12)]
    first = kpi.export(events)
    shuffled = events[:]
    random.Random(7).shuffle(shuffled)
    assert kpi.export(shuffled) == first


def test_csv_has_the_documented_columns_and_flat_values():
    e = ev(1, "2026-10-01T10:00:00+00:00", findings_brief=brief("missing-tests", "missing-tests", "xss"))
    rows = list(csv.DictReader(io.StringIO(kpi.export([e])["kpi-runs.csv"])))
    assert list(rows[0].keys()) == kpi.COLUMNS
    assert rows[0]["phases"] == "3;4;5;8" and rows[0]["categories"] == "missing-tests:2;xss:1"
    assert rows[0]["week"] == "2026-W40" and rows[0]["blocked"] == "false"


# ----------------------------------------------------------------------------- the KPIs

def test_rates_counts_and_quantiles():
    events = [
        ev(1, "2026-10-01T09:00:00+00:00", "fail", counts={"blocker": 1, "high": 2, "medium": 4}, failed_phases=[4, 8],
           findings_brief=brief("secret-exposure"), unverified_count=1, duration_s=10.0),
        ev(2, "2026-10-01T10:00:00+00:00", "pass", counts={"medium": 3}, duration_s=20.0),
        ev(3, "2026-10-02T10:00:00+00:00", "pass", duration_s=30.0, llm_usage={"prompt_tokens": 0, "completion_tokens": 0},
           skip={"requested": True, "valid": True, "requested_phases": [5], "valid_phases": [5], "reason": "Spike SPK-1", "errors": []}),
        ev(4, "2026-10-02T11:00:00+00:00", "pass", duration_s=40.0),
    ]
    k = kpi.compute_kpis(kpi.build_rows(events))
    assert k["runs"] == 4
    assert k["gate_pass_rate"] == 0.75 and k["block_rate"] == 0.25
    assert k["blocking_findings_per_run"] == 0.75  # (1 blocker + 2 high) / 4 runs
    assert k["phase_fail_rate"] == {"3": 0.0, "4": 0.25, "5": 0.0, "8": 0.25}
    assert k["security_critical_run_rate"] == 0.25
    assert k["skip_request_rate"] == 0.25 and k["skip_granted_rate"] == 0.25
    assert k["unverified_finding_share"] == round(1 / 10, 4)  # 1 unverified of 10 findings
    assert k["gate_latency_s_p50"] == 25.0
    assert k["tokens_per_run"] == 1200 and k["token_metered_share"] == 0.75  # the unmetered run is left out
    assert k["blocking_findings_per_kloc"] is None  # needs a changed-lines field the events do not carry yet


def test_first_time_right_and_time_to_green():
    events = [
        # feature/a: fails, then green 3 h later, fails again, green 1 h later -> two recoveries.
        ev(1, "2026-10-01T09:00:00+00:00", "fail", ref="feature/a"),
        ev(2, "2026-10-01T10:00:00+00:00", "fail", ref="feature/a"),
        ev(3, "2026-10-01T12:00:00+00:00", "pass", ref="feature/a"),
        ev(4, "2026-10-02T09:00:00+00:00", "fail", ref="feature/a"),
        ev(5, "2026-10-02T10:00:00+00:00", "pass", ref="feature/a"),
        # feature/b: green first time.
        ev(6, "2026-10-01T09:30:00+00:00", "pass", ref="feature/b"),
        # feature/c: never turns green, so it adds no recovery.
        ev(7, "2026-10-01T09:45:00+00:00", "fail", ref="feature/c"),
        # Unattributable runs are left out of both KPIs.
        ev(8, "2026-10-01T09:50:00+00:00", "fail", ref="HEAD"),
        ev(9, "2026-10-01T09:55:00+00:00", "fail", repo="unknown/unknown"),
    ]
    rows = kpi.build_rows(events)
    assert kpi.first_time_right(rows) == (1, 3)
    assert sorted(kpi.time_to_green_hours(rows)) == [1.0, 3.0]
    k = kpi.compute_kpis(rows)
    assert k["time_to_green_hours_median"] == 2.0 and k["time_to_green_recoveries"] == 2
    assert k["attributable_share"] == round(7 / 9, 4)


def test_missing_data_gives_none_not_zero():
    k = kpi.compute_kpis([])
    assert k["runs"] == 0
    for key in ("gate_pass_rate", "first_time_right_rate", "block_rate", "time_to_green_hours_median",
                "unverified_finding_share", "gate_latency_s_p50", "tokens_per_run"):
        assert k[key] is None, key
    files = kpi.export([])
    assert "No gate runs in the dataset." in files["kpi-dashboard.html"]


def test_summary_splits_by_week_and_repo():
    events = [ev(1, "2026-09-29T10:00:00+00:00", repo="org/a"), ev(2, "2026-10-06T10:00:00+00:00", "fail", repo="org/b")]
    s = kpi.kpi_summary(kpi.build_rows(events))
    assert list(s["weeks"]) == ["2026-W40", "2026-W41"]
    assert s["repos"]["org/a"]["gate_pass_rate"] == 1.0 and s["repos"]["org/b"]["gate_pass_rate"] == 0.0


# ----------------------------------------------------------------------------- the dashboard

def test_dashboard_embeds_data_safely_and_has_no_external_scripts():
    evil = "</script><script>alert(1)</script><!--"
    e = ev(1, "2026-10-01T10:00:00+00:00",
           skip={"requested": True, "valid": False, "requested_phases": [4], "valid_phases": [], "reason": evil, "errors": []})
    html = kpi.export([e])["kpi-dashboard.html"]
    assert evil not in html and "alert(1)</script>" not in html
    assert len(re.findall(r"<script\b", html)) == 2  # the data block and the page script, nothing injected
    assert not re.search(r"<script[^>]+src=", html)
    payload = re.search(r'<script id="kpi-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    data = json.loads(payload)
    assert data["summary"]["skip_reasons"][0]["reason"] == evil[:200]
    assert "textContent" in html and "innerHTML" not in html


def test_hostile_repo_names_and_comment_closers_stay_data():
    """Repository names reach option values and table cells; `-->` must not matter without a `<!--` before it."""
    hostile = 'org/x"><img src=x onerror=alert(1)>'
    e = ev(1, "2026-10-01T10:00:00+00:00",
           skip={"requested": True, "valid": True, "requested_phases": [4], "valid_phases": [4], "reason": "--> <!-- -->", "errors": []})
    e["repo"] = hostile  # not a valid slug, but the exporter must stay safe whatever reaches it
    html = kpi.export([e])["kpi-dashboard.html"]
    data_block = re.search(r'<script id="kpi-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "<" not in data_block  # so neither `</script` nor `<!--` can occur, and `-->` alone is inert
    assert "<img" not in html and hostile not in html
    data = json.loads(data_block)
    assert hostile in data["summary"]["repos"] and data["summary"]["skip_reasons"][0]["reason"] == "--> <!-- -->"
    page_script = html.split('<script>', 1)[1]
    assert "innerHTML" not in page_script and "outerHTML" not in page_script and "insertAdjacentHTML" not in page_script
    assert "document.write" not in page_script and "aria-label" not in page_script


def test_dashboard_ships_a_strict_content_security_policy():
    import base64
    import hashlib

    html = kpi.export([ev(1, "2026-10-01T10:00:00+00:00")])["kpi-dashboard.html"]
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html).group(1)
    assert "default-src 'none'" in csp and "connect-src 'none'" in csp and "base-uri 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    # The hashes must match what the browser will see, or the page would silently not run.
    for tag, directive in (("script", "script-src"), ("style", "style-src")):
        body = re.search(rf"<{tag}>(.*?)</{tag}>", html, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        assert f"{directive} 'sha256-{digest}'" in csp
    assert ' style="' not in html  # hash-pinned styles do not cover style attributes


def test_render_dashboard_uses_the_one_o_palette():
    html = render_dashboard(kpi.kpi_summary([]))
    for token in ("#434098", "#EB001F", "#EDECFC", "Lexend", "Source Sans 3"):
        assert token in html


# ----------------------------------------------------------------------------- the CLI

def test_cli_kpi_export_writes_all_artefacts(tmp_path):
    from ai_sdlc_gate.cli import main

    events_dir = tmp_path / "events"
    for i, verdict in enumerate(["fail", "pass", "pass"]):
        ingest_event(ev(i, f"2026-10-0{i + 1}T10:00:00+00:00", verdict), events_dir)
    out = tmp_path / "kpi"
    assert main(["kpi", "export", "--events-dir", str(events_dir), "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["kpi-dashboard.html", "kpi-runs.csv", "kpi-runs.json", "kpi-summary.json", "kpi-triage.csv"]
    summary = json.loads((out / "kpi-summary.json").read_text(encoding="utf-8"))
    assert summary["overall"]["runs"] == 3 and summary["overall"]["gate_pass_rate"] == pytest.approx(0.6667)
