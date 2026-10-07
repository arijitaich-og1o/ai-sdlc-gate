"""Follow-up KPIs: changed lines in events, finding triage (false-positive rate) and the time-saved estimate."""
from __future__ import annotations

import json

import pytest

from ai_sdlc_gate import kpi, triage
from ai_sdlc_gate.changes import ChangedFile, ChangeSet
from ai_sdlc_gate.cli import main
from ai_sdlc_gate.intent import detect_intent
from ai_sdlc_gate.llm import StaticLLM
from ai_sdlc_gate.metrics import build_event, validate_event
from ai_sdlc_gate.runner import run_gate
from ai_sdlc_gate.skills import load_skills
from ai_sdlc_gate.skip import parse_skip
from tests.test_kpi import ev

DIFF = "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,3 @@\n context\n-old = 1\n+new = 1\n+added = 2\n"


def _report(cfg, skills_dir, findings):
    cs = ChangeSet(files=[ChangedFile(path="app.py", status="M", diff=DIFF, content="context\nnew = 1\nadded = 2\n")], branch="feature/x")
    llm = StaticLLM(lambda s, u: {"summary": "ok", "findings": findings})
    return run_gate(cfg, llm, load_skills(skills_dir, cfg), cs, detect_intent(cfg, explicit="commit"), parse_skip(cfg, []),
                    context={"repo": "org/app", "actor": "dev-one"})


def _finding(fid="f1", cat="missing-tests", sev="high", title="No test for `new`"):
    return {"id": fid, "severity": sev, "category": cat, "title": title, "description": "d", "file": "app.py", "line": 2,
            "recommendation": "r", "confidence": 0.9}


# ----------------------------------------------------------------------------- changed lines

def test_line_counts_skip_file_headers():
    cs = ChangeSet(files=[ChangedFile(path="app.py", status="M", diff=DIFF), ChangedFile(path="b.py", status="A", diff="+x\n+y\n")])
    assert cs.line_counts() == (4, 1)


def test_event_carries_changed_lines_and_old_reports_do_not_fake_them(cfg, skills_dir):
    report = _report(cfg, skills_dir, [])
    event = build_event(report)
    assert (event["lines_added"], event["lines_removed"]) == (2, 1) and not validate_event(event)
    del report.stats["lines_added"]
    assert "lines_added" not in build_event(report)  # absent, not 0: an old engine's run is not an empty change


def test_blocking_findings_per_kloc_counts_only_sized_runs():
    sized = ev(1, "2026-10-01T10:00:00+00:00", "fail", counts={"high": 2}, lines_added=150, lines_removed=50)
    unsized = ev(2, "2026-10-01T11:00:00+00:00", "fail", counts={"high": 9})
    k = kpi.compute_kpis(kpi.build_rows([sized, unsized]))
    assert k["blocking_findings_per_kloc"] == 10.0  # 2 findings / 200 lines, the unsized run is left out
    assert k["sized_run_share"] == 0.5
    assert kpi.export([sized])["kpi-runs.csv"].splitlines()[1].endswith(",150,50,org")  # then the team column


# ----------------------------------------------------------------------------- triage

def test_triage_keeps_title_path_and_note_on_the_machine(tmp_path):
    report = {"generated_at": "2026-10-07T10:00:00+00:00", "phases": [{"phase": 5, "findings": [_finding()]}]}
    f = triage.report_findings(report)[0]
    triage.record(tmp_path, report, f, "false-positive", note="the test is in tests/test_app.py")
    sent = triage.for_event(triage.pending(tmp_path))
    assert sent == [{"phase": 5, "category": "missing-tests", "severity": "high", "label": "false-positive", "run_ts": "2026-10-07T10:00:00+00:00"}]
    blob = json.dumps(sent)
    assert "app.py" not in blob and "No test" not in blob and "test_app" not in blob and "f1" not in blob


def test_relabelling_replaces_the_unsent_label_and_sent_labels_stay(tmp_path):
    report = {"generated_at": "t1", "phases": [{"phase": 4, "findings": [_finding()]}]}
    f = triage.report_findings(report)[0]
    triage.record(tmp_path, report, f, "false-positive")
    triage.record(tmp_path, report, f, "accepted")
    assert [e["label"] for e in triage.pending(tmp_path)] == ["accepted"]
    triage.mark_sent(tmp_path, [e["id"] for e in triage.pending(tmp_path)])
    assert triage.pending(tmp_path) == []
    triage.record(tmp_path, report, f, "wont-fix")  # a later change of mind is a new label, the sent one stays
    assert [e["label"] for e in triage.load(tmp_path)] == ["accepted", "wont-fix"]
    with pytest.raises(ValueError):
        triage.record(tmp_path, report, f, "maybe")


def test_cli_triage_lists_and_labels(tmp_path, monkeypatch, capsys, cfg, skills_dir):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    report = _report(cfg, skills_dir, [_finding("f1"), _finding("f2", cat="xss", sev="blocker", title="Unescaped output")])
    (tmp_path / "last-report.json").write_text(json.dumps(report.to_dict()), encoding="utf-8")
    assert main(["triage"]) == 0
    listing = capsys.readouterr().out
    assert "missing-tests" in listing and "Label one with" in listing
    n = next(line.split(".")[0].strip() for line in listing.splitlines() if "xss" in line)
    assert main(["triage", n, "--label", "false-positive", "--note", "framework escapes it"]) == 0
    assert [(e["category"], e["label"]) for e in triage.pending(tmp_path)] == [("xss", "false-positive")]
    assert main(["triage", "99", "--label", "accepted"]) != 0
    assert main(["triage"]) == 0 and "-> false-positive" in capsys.readouterr().out


def test_emit_metrics_carries_labels_and_marks_them_sent_only_after_dispatch(tmp_path, monkeypatch, cfg, skills_dir):
    from ai_sdlc_gate import cli, ghauth, metrics

    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    report = _report(cfg, skills_dir, [_finding()])
    rpath = tmp_path / "last-report.json"
    rpath.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    triage.record(tmp_path, report.to_dict(), triage.report_findings(report.to_dict())[0], "false-positive")
    monkeypatch.setattr(ghauth, "find_credential", lambda **kw: ghauth.GitHubCredential(token="t", username="dev-one", source="test"))
    sent = []

    def fail(event, repo, token, event_type):
        raise RuntimeError("offline")

    monkeypatch.setattr(metrics, "dispatch_event", fail)
    assert cli.main(["emit-metrics", "--report", str(rpath), "--dispatch", "--output", str(tmp_path / "e.json")]) != 0
    assert len(triage.pending(tmp_path)) == 1  # not lost when the dispatch fails
    monkeypatch.setattr(metrics, "dispatch_event", lambda event, *a: sent.append(event))
    assert cli.main(["emit-metrics", "--report", str(rpath), "--dispatch", "--output", str(tmp_path / "e.json")]) == 0
    # The stand-in model reports the finding in every phase; the first one listed (phase 3) is the one labelled.
    assert sent[0]["triage"] == [{"phase": 3, "category": "missing-tests", "severity": "high", "label": "false-positive", "run_ts": report.generated_at}]
    assert not validate_event(sent[0])
    assert triage.pending(tmp_path) == []


# ----------------------------------------------------------------------------- false-positive rate

def _labelled(n_fp: int, n_ok: int, phase: int = 4, cat: str = "missing-tests") -> dict:
    labels = [{"phase": phase, "category": cat, "severity": "high", "label": "false-positive", "run_ts": "x"}] * n_fp
    labels += [{"phase": phase, "category": cat, "severity": "high", "label": "accepted", "run_ts": "x"}] * n_ok
    return ev(100 + n_fp + 10 * n_ok + phase, "2026-10-03T10:00:00+00:00", triage=labels)


def test_feedback_needs_enough_labels_and_reports_coverage():
    few = kpi.export([_labelled(2, 3)])
    s = json.loads(few["kpi-summary.json"])["overall"]["feedback"]
    assert s["labels"] == 5 and s["rate"] is None and s["positive_share"] is None

    events = [_labelled(3, 9, phase=4), _labelled(1, 1, phase=8, cat="xss")]
    s = json.loads(kpi.export(events)["kpi-summary.json"])["overall"]["feedback"]
    assert s["labels"] == 14 and s["rate"] == round(4 / 14, 4)
    assert s["positive_share"] == round(10 / 14, 4)  # accepted / (accepted + false-positive)
    assert s["label_coverage"] is None  # the labelled runs report no findings of their own: coverage undefined
    assert s["by_phase"]["4"] == {"labels": 12, "rate": 0.25}
    assert s["by_phase"]["8"] == {"labels": 2, "rate": None}  # too few in that group
    assert s["label_counts"] == {"accepted": 10, "false-positive": 4}
    assert kpi.export(events)["kpi-triage.csv"].splitlines()[0] == ",".join(kpi.TRIAGE_COLUMNS)


# ----------------------------------------------------------------------------- blocks resolved (measured)

def test_blocks_count_once_per_streak_and_only_resolved_ones_count_as_fixed():
    rows = kpi.build_rows([
        ev(1, "2026-10-01T09:00:00+00:00", "fail", counts={"high": 3}),
        ev(2, "2026-10-01T10:00:00+00:00", "fail", counts={"high": 3}),  # same findings again: not counted twice
        ev(3, "2026-10-01T11:00:00+00:00", "pass"),
        ev(4, "2026-10-02T09:00:00+00:00", "fail", counts={"blocker": 1, "high": 1}),  # never turns green
        ev(5, "2026-10-02T09:30:00+00:00", "fail", ref="HEAD", counts={"high": 7}),  # unattributable: left out
    ])
    k = kpi.compute_kpis(rows)
    assert (k["blocks"], k["blocks_resolved"], k["blocking_findings_resolved"]) == (2, 1, 3)
    assert k["time_to_green_hours_median"] == 2.0 and k["fix_iterations_median"] == 2.0


def test_nothing_is_estimated_from_assumed_parameters():
    """Arijit, 2026-10-07: "we cannot have any assumption". No assumed constant, no estimated KPI."""
    assert not hasattr(kpi, "TIME_SAVED_ASSUMPTIONS") and not hasattr(kpi, "time_saved")
    summary = json.loads(kpi.export([ev(1, "2026-10-01T09:00:00+00:00", "fail", counts={"high": 2})])["kpi-summary.json"])
    blob = json.dumps(summary).lower()
    for word in ("assum", "time_saved", "precision", "estimate"):
        assert word not in blob, word
