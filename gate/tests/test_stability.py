from __future__ import annotations

from pathlib import Path

from ai_sdlc_gate import ledger as lg
from ai_sdlc_gate.changes import ChangedFile, ChangeSet
from ai_sdlc_gate.intent import detect_intent
from ai_sdlc_gate.llm import StaticLLM
from ai_sdlc_gate.progress import Progress
from ai_sdlc_gate.runner import merge_findings, review_passes, review_phase, run_gate, skill_categories
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


def test_review_runs_until_a_pass_finds_nothing_new(cfg, skills_dir):
    """Pass 1 finds one issue, pass 2 another, pass 3 a third, pass 4 nothing -> 4 passes, converged."""
    skill = load_skills(skills_dir, cfg)[4]
    it = detect_intent(cfg, explicit="commit")
    per_pass = {
        1: [_f()],
        2: [_f(cat="hardcoded-credential", title="password literal", line=3)],
        3: [_f(cat="debug-statement", title="print left in code", line=6, sev="medium")],
    }
    seen: list[int] = []

    def responder(system, user):
        n = 1
        if "<review_pass" in user:
            n = int(user.split('number="', 1)[1].split('"', 1)[0])
        seen.append(n)
        return {"summary": "s", "findings": per_pass.get(n, [])}

    assert review_passes(cfg) == (2, 4)
    res = review_phase(cfg, StaticLLM(responder), skill, _cs(), it, max_passes=6)
    assert seen == [1, 2, 3, 4] and res.passes == 4 and res.converged
    assert sorted(f["category"] for f in res.findings) == ["debug-statement", "hardcoded-credential", "sql-injection"]
    # The pass limit stops the loop even while new findings keep coming, and says so.
    seen.clear()
    endless = StaticLLM(lambda s, u: {"summary": "", "findings": [_f(cat="dead-code", title=f"unused {len(seen)}", line=len(seen) * 10 + 1)] if not seen.append(1) else []})
    res2 = review_phase(cfg, endless, skill, _cs(), it, max_passes=3)
    assert res2.passes == 3 and not res2.converged and len(res2.findings) == 3
    # A clean change stops after the minimum number of passes.
    seen.clear()
    res3 = review_phase(cfg, StaticLLM(lambda s, u: {"summary": "", "findings": []}), skill, _cs(), it)
    assert res3.passes == 2 and res3.converged


def test_progress_events_and_report_depth(cfg, skills_dir):
    import io

    skills = load_skills(skills_dir, cfg)
    it = detect_intent(cfg, explicit="commit")
    out = io.StringIO()
    prog = Progress(stream=out, enabled=True, interactive=False)
    calls: list[int] = []

    def responder(system, user):
        calls.append(1)
        return {"summary": "", "findings": [_f()] if len(calls) == 1 else []}

    report = run_gate(cfg, StaticLLM(responder), skills, _cs(), it, parse_skip(cfg, []), progress=prog)
    text = out.getvalue()
    assert "Reviewing 1 file(s) for phase(s)" in text
    assert "pass 1 done, 1 finding(s); taking another look" in text
    assert "pass 2 done, nothing new" in text
    assert "Review finished in" in text and "BLOCKED" in text
    assert report.stats["review"]["converged"] and report.stats["review"]["passes"]
    from ai_sdlc_gate.report import to_markdown, to_text

    rendered = to_text(report)
    assert "Review passes (" in rendered and "found nothing new, so this list is complete" in rendered
    assert "| Passes |" in to_markdown(report, cfg)

    # Interactive mode redraws one line with a bar and clears it at the end; nothing is written when disabled.
    tty = io.StringIO()
    prog2 = Progress(stream=tty, enabled=True, interactive=True)
    prog2.start([(4, "development")], 1)
    prog2.phase_start(4, "development", 1, 2)
    prog2.pass_start(4, "development", 1, 2)
    prog2.pass_done(4, "development", 1, 1, 1, True)
    prog2.finish("passed")
    drawn = tty.getvalue()
    assert "\r[ai-sdlc-gate] [" in drawn and "%" in drawn and "Review finished" in drawn
    off = io.StringIO()
    Progress(stream=off, enabled=False).start([(4, "development")], 1)
    assert off.getvalue() == ""


def test_gateway_errors_never_reveal_model_or_key(monkeypatch):
    import httpx

    from ai_sdlc_gate.llm import LLMClient, LLMError, describe_failure

    body = '{"error":{"message":"Budget has been exceeded! Key=Some-Team-key (sk-...ABCD) Current cost: 50.1, Max budget: 50.0","type":"budget_exceeded"}}'
    assert "budget" in describe_failure(429, body) and "sk-" not in describe_failure(429, body)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, content=body.encode())

    client = LLMClient(base_url="https://gw.example", api_key="sk-x", model="secret-model-name", fallback_models=["other-secret"], max_retries=3)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client._sleep = lambda s: None
    with __import__("pytest").raises(LLMError) as exc:
        client.chat("s", "u")
    msg = str(exc.value)
    assert "secret-model-name" not in msg and "other-secret" not in msg and "sk-" not in msg and "Some-Team" not in msg
    assert "usage budget" in msg and "gate administrators" in msg
    assert len(calls) == 2, "an exhausted budget is final: no retries, one attempt per model"
