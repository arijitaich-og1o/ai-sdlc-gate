from __future__ import annotations

from pathlib import Path

from ai_sdlc_gate import ledger as lg
from ai_sdlc_gate.changes import ChangedFile, ChangeSet
from ai_sdlc_gate.intent import detect_intent
from ai_sdlc_gate.llm import StaticLLM
from ai_sdlc_gate.runner import merge_findings, review_phase, run_gate, skill_categories
from ai_sdlc_gate.skills import load_skills
from ai_sdlc_gate.skip import parse_skip


def _f(sev="high", cat="sql-injection", title="SQL built by f-string", file="app.py", line=10, conf=0.9):
    return {"id": f"{cat}-{line}", "severity": sev, "category": cat, "title": title, "description": "d", "file": file, "line": line, "recommendation": "r", "confidence": conf}


CODE = "import os\nq = f\"SELECT * FROM t WHERE id={uid}\"\nPASSWORD_ENV = os.environ['PW']\nx = 1\ny = 2\nprint(q)\n"


def _cs():
    return ChangeSet(files=[ChangedFile(path="app.py", status="M", diff="+x", content=CODE)], branch="feature/x")


def test_skill_categories_are_extracted(cfg, skills_dir):
    cats = skill_categories(load_skills(skills_dir, cfg)[4])
    assert "sql-injection" in cats and "secret-exposure" in cats and len(cats) > 20


def test_merge_findings_dedupes_near_duplicates():
    a = [_f(line=10), _f(cat="dead-code", title="unused import", line=1, sev="low")]
    b = [_f(line=12, title="SQL built by f-string in query", conf=0.95, sev="blocker"), _f(cat="xss", title="reflected input", line=40),
         _f(cat="sql-injection", title="second, different query concatenates user input", line=11)]
    merged = merge_findings(a, b)
    assert len(merged) == 4  # the third sql-injection finding has a different title and stays separate
    sql = next(f for f in merged if f["category"] == "sql-injection")
    assert sql["severity"] == "blocker"  # higher severity wins


def test_second_look_pass_receives_first_pass_findings(cfg, skills_dir):
    skill = load_skills(skills_dir, cfg)[4]
    calls: list[str] = []

    def responder(system, user):
        calls.append(user)
        if "<review_pass" in user:
            assert "Already reported" in user and "SQL built by f-string" in user and "Taxonomy categories with no finding yet" in user
            return {"summary": "", "findings": [_f(cat="hardcoded-credential", title="password literal", line=3)]}
        return {"summary": "first", "findings": [_f()]}

    res = review_phase(cfg, StaticLLM(responder), skill, _cs(), detect_intent(cfg, explicit="commit"), passes=2)
    assert len(calls) == 2 and res.passes == 2
    assert sorted(f["category"] for f in res.findings) == ["hardcoded-credential", "sql-injection"]


def test_ledger_known_resolved_and_late(tmp_path):
    lines = {"app.py": CODE.splitlines()}
    led = lg.Ledger()
    # run 1: one finding on line 2
    c1 = lg.apply_ledger(led, [_f(line=2)], lines, non_skippable=set())
    assert c1 == {"known": 0, "new": 1, "late": 0, "resolved": 0} and led.runs == 1
    # run 2: same finding (slightly different title/line) is known; a new finding on already-reviewed line 6 is late;
    # a blocker on reviewed code still counts as new (never advisory).
    f_known = _f(line=3, title="SQL query built via f-string")
    f_late = _f(cat="debug-statement", title="print left in code", line=6, sev="medium")
    f_block = _f(cat="secret-exposure", title="secret", line=6, sev="blocker")
    c2 = lg.apply_ledger(led, [f_known, f_late, f_block], lines, non_skippable={"secret-exposure"})
    assert f_known["known"] and f_late.get("late") and not f_block.get("late")
    assert c2["known"] == 1 and c2["late"] == 1 and c2["new"] == 1 and c2["resolved"] == 0
    # run 3: the known finding is fixed (not reported) -> resolved
    c3 = lg.apply_ledger(led, [], lines, non_skippable=set())
    assert c3["resolved"] == 3 and led.findings == []
    path = tmp_path / "l.json"
    led.save(path)
    assert lg.Ledger.load(path).runs == 3


def test_run_gate_with_ledger_makes_late_findings_advisory(cfg, skills_dir, tmp_path):
    skills = load_skills(skills_dir, cfg)
    led = lg.Ledger()
    it = detect_intent(cfg, explicit="commit")
    # run 1 reports the SQL finding -> blocked
    r1 = run_gate(cfg, StaticLLM(lambda s, u: {"summary": "", "findings": [_f(line=2)]}), skills, _cs(), it, parse_skip(cfg, []), ledger=led)
    assert r1.verdict == "fail" and led.runs == 1
    # run 2: developer fixed it; the model now flags a different high issue on an already-reviewed line -> late, advisory
    seen_known: list[str] = []

    def responder(system, user):
        if "<previously_reported>" in user:
            seen_known.append(user)
        return {"summary": "", "findings": [_f(cat="debug-statement", title="print left in code", line=6)]}

    r2 = run_gate(cfg, StaticLLM(responder), skills, _cs(), it, parse_skip(cfg, []), ledger=led)
    assert seen_known and "SQL built by f-string" in seen_known[0]
    assert r2.verdict == "pass"
    assert all(f.get("late") for p in r2.phases for f in p.findings)
    assert r2.stats["stability"]["late"] >= 1 and r2.stats["stability"]["resolved"] >= 1
    from ai_sdlc_gate.report import to_text

    text = to_text(r2)
    assert "Late findings (advisory)" in text and "PASSED" in text
    # a secret on reviewed code is never advisory
    r3 = run_gate(cfg, StaticLLM(lambda s, u: {"summary": "", "findings": [_f(cat="secret-exposure", sev="blocker", title="key", line=6)]}), skills, _cs(), it, parse_skip(cfg, []), ledger=led)
    assert r3.verdict == "fail"
