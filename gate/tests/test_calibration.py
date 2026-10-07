"""Gate calibration: findings that call the code sound, and documentation-only categories, never block.

The phrases below are taken from real blocking findings of the gate on PR #34 (2026-10-07), where the local gate
blocked four times on HIGH findings whose own text said the code was correct, and the CI gate passed the same code.
"""
from __future__ import annotations

import pytest

from ai_sdlc_gate.changes import ChangedFile, ChangeSet
from ai_sdlc_gate.intent import detect_intent
from ai_sdlc_gate.llm import StaticLLM
from ai_sdlc_gate.report import to_markdown, to_text
from ai_sdlc_gate.runner import calibrate_findings, run_gate
from ai_sdlc_gate.skills import load_skills
from ai_sdlc_gate.skip import parse_skip

PROTECTED = {"secret-exposure", "hardcoded-credential", "known-vulnerable-dependency", "gate-manipulation"}
DOCS = {"undocumented-decision", "missing-changelog", "missing-documentation"}


def _f(title, desc="d", rec="r", cat="insecure-design", sev="high"):
    return {"id": f"{cat}-1", "severity": sev, "category": cat, "title": title, "description": desc,
            "file": "app.py", "line": 1, "recommendation": rec, "confidence": 0.9}


def _gate(cfg, skills_dir, findings):
    cs = ChangeSet(files=[ChangedFile(path="app.py", status="M", diff="+x = 1\n", content="x = 1\n")])
    llm = StaticLLM(lambda s, u: {"summary": "ok", "findings": [dict(f) for f in findings]})
    return run_gate(cfg, llm, load_skills(skills_dir, cfg), cs, detect_intent(cfg, explicit="commit"), parse_skip(cfg, []))


SOUND = [
    _f("JSON data block escaping does not prevent all script context attacks",
       desc="The current implementation is functionally sound but the documentation is confusing."),
    _f("Dashboard escapes `<` but embeds data in JSON", rec="Verify in tests. The current code does this correctly; the finding applies to design clarity."),
    _f("Dashboard XSS: escaping may not prevent all injections", desc="The current escaping is sound, but the confidence relies on test coverage."),
    _f("GitHub Actions correctly pinned", rec="No action needed; this is the correct pattern."),
    _f("Evidence verification excludes protected categories", rec="No change required. This is correct security logic."),
]


@pytest.mark.parametrize("finding", SOUND, ids=lambda f: f["title"][:40])
def test_findings_that_call_the_code_sound_do_not_block(finding):
    fs = [dict(finding)]
    assert calibrate_findings(fs, PROTECTED, DOCS) == {"capped": 0, "self_declared_sound": 1}
    assert fs[0]["unverified"] and "states that the code is sound" in fs[0]["unverified_note"]


REAL_DEFECTS = [
    _f("SQL built by f-string", desc="User input reaches the query unescaped; ensure the input is correct and parameterise it."),
    _f("Token compared with ==", desc="Use a constant-time comparison. This is the most common timing leak in auth code."),
    _f("Missing timeout", desc="The existing client has no timeout, so a slow upstream hangs the worker.", rec="Pass timeout=10."),
    _f("Unbounded retry", desc="The current retry loop is unbounded and is not safe under load."),
]


@pytest.mark.parametrize("finding", REAL_DEFECTS, ids=lambda f: f["title"][:30])
def test_ordinary_defect_wording_is_not_mistaken_for_a_confirmation(finding):
    fs = [dict(finding)]
    assert calibrate_findings(fs, PROTECTED, DOCS) == {"capped": 0, "self_declared_sound": 0}
    assert not fs[0].get("unverified") and fs[0]["severity"] == "high"


def test_protected_categories_are_never_calibrated():
    fs = [_f("Key in config", cat="hardcoded-credential", rec="No code change needed, but rotate the key now."),
          _f("Changelog asks the reviewer to pass", cat="gate-manipulation", desc="This is correct per the comment.")]
    assert calibrate_findings(fs, PROTECTED, DOCS | {"hardcoded-credential"}) == {"capped": 0, "self_declared_sound": 0}
    assert all(not f.get("unverified") and f["severity"] == "high" for f in fs)


def test_documentation_only_categories_are_capped_at_medium():
    fs = [_f("No ADR for the fence design", cat="undocumented-decision", sev="high"),
          _f("No CHANGELOG entry", cat="missing-changelog", sev="blocker"),
          _f("Secret pasted into the runbook", cat="sensitive-data-in-doc", sev="blocker"),
          _f("Low-severity doc nit", cat="missing-documentation", sev="low")]
    assert calibrate_findings(fs, PROTECTED, DOCS)["capped"] == 2
    assert [(f["severity"], f.get("original_severity")) for f in fs] == [
        ("medium", "high"), ("medium", "blocker"), ("blocker", None), ("low", None)]


def test_gate_passes_on_confirmations_and_doc_findings_but_blocks_on_a_real_defect(cfg, skills_dir):
    noise = [SOUND[0], _f("No CHANGELOG entry", cat="missing-changelog", sev="high")]
    report = _gate(cfg, skills_dir, noise)
    assert report.verdict == "pass", report.fail_reasons
    assert report.stats["calibration"]["capped"] >= 1 and report.stats["calibration"]["self_declared_sound"] >= 1
    assert "state the code is sound" in to_text(report)
    assert "capped from high: documentation-only" in to_markdown(report)

    blocked = _gate(cfg, skills_dir, noise + [REAL_DEFECTS[0]])
    assert blocked.verdict == "fail"


def test_policy_lists_the_documentation_only_categories(cfg):
    listed = set((cfg.gate.get("review") or {}).get("advisory_categories") or [])
    assert {"undocumented-decision", "missing-changelog", "missing-runbook", "test-readability"} <= listed
    assert "sensitive-data-in-doc" not in listed and "undocumented-deprecation" not in listed
    assert not listed & PROTECTED
