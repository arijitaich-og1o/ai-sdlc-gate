from __future__ import annotations

from pathlib import Path

import yaml

from ai_sdlc_gate.evaluate import evaluate_skill, load_ground_truth
from ai_sdlc_gate.judge import apply_decision, bump_version, decision_markdown, judge
from ai_sdlc_gate.llm import StaticLLM
from ai_sdlc_gate.skills import load_skills, parse_skill


def _gt_findings(trials_root: Path, slug: str, fraction: float = 1.0):
    gt = load_ground_truth(trials_root / slug)
    defects = gt["defects"]
    n = max(1, int(len(defects) * fraction))
    return [
        {"id": d["id"], "severity": d["severity"], "category": "general", "title": d["title"], "description": " ".join(d["keywords"]),
         "file": d["file"], "line": 1, "recommendation": "fix", "confidence": 0.9}
        for d in defects[:n]
    ]


def _llm_for(findings):
    def responder(system, user):
        if "<extra_findings>" in user:
            return {"legitimate": {}, "clarity": 0.8, "notes": "n"}
        return {"summary": "s", "findings": findings}

    return StaticLLM(responder)


def test_ground_truth_files_load_for_all_phases(cfg, trials_root):
    for phase in range(1, 9):
        gt = load_ground_truth(trials_root / cfg.phase_slug(phase))
        assert gt["phase"] == phase and len(gt["defects"]) >= 5
        for d in gt["defects"]:
            assert (trials_root / d["file"]).is_file(), d["file"]


def test_evaluate_scores_recall_and_precision(cfg, skills_dir, trials_root):
    skills = load_skills(skills_dir, cfg)
    skill = skills[4]
    full = evaluate_skill(cfg, _llm_for(_gt_findings(trials_root, "04-development")), skill, trials_root)
    assert full.recall == 1.0 and full.precision == 1.0 and full.missed == []
    assert full.score > 0.9

    half = evaluate_skill(cfg, _llm_for(_gt_findings(trials_root, "04-development", 0.5)), skill, trials_root)
    assert 0.4 <= half.recall <= 0.6 and half.score < full.score

    empty = evaluate_skill(cfg, StaticLLM(), skill, trials_root)
    assert empty.recall == 0.0 and empty.score == 0.0


def test_evaluate_excludes_ground_truth_from_reviewed_content(cfg, skills_dir, trials_root, monkeypatch):
    llm = _llm_for([])
    evaluate_skill(cfg, llm, load_skills(skills_dir, cfg)[4], trials_root)
    system, user = llm.calls[0]
    assert "GROUND_TRUTH" not in user and 'path="04-development/app.py"' in user

    # A relative trials root (as passed by the CLI from the repository root) must collect the same files.
    monkeypatch.chdir(trials_root.parent)
    rel = _llm_for([])
    ev = evaluate_skill(cfg, rel, load_skills(skills_dir, cfg)[4], Path("trials"))
    assert ev.error is None and 'path="04-development/app.py"' in rel.calls[0][1]

    import pytest

    with pytest.raises(FileNotFoundError):
        evaluate_skill(cfg, _llm_for([]), load_skills(skills_dir, cfg)[4], Path("does-not-exist"))


def _candidate_from(skill, extra="\n\n## Extra section\nAlso check for hard-coded tenant identifiers.\n", version="1.1.0"):
    fm = dict(skill.frontmatter)
    fm["version"] = version
    from ai_sdlc_gate.skills import render_skill

    return parse_skill(render_skill(fm, skill.body + extra), slug=skill.slug)


def test_judge_keeps_current_when_candidate_is_not_better(cfg, skills_dir, trials_root):
    base = load_skills(skills_dir, cfg)[4]
    cand = _candidate_from(base)
    review = _llm_for(_gt_findings(trials_root, "04-development"))  # both score identically
    arbiter = StaticLLM(lambda s, u: {"decision": "replace", "rationale": "shiny", "absorbed_sections": [], "merged_body": None, "version_bump": "minor"})
    d = judge(cfg, review, arbiter, base, cand, trials_root)
    assert d.decision == "keep_current"
    assert any("replace requires" in g for g in d.guards)
    assert d.resolved_markdown == base.markdown


def test_judge_replaces_when_candidate_clearly_better(cfg, skills_dir, trials_root):
    base = load_skills(skills_dir, cfg)[4]
    cand = _candidate_from(base)
    calls = {"n": 0}
    full = _gt_findings(trials_root, "04-development")

    def responder(system, user):
        if "<extra_findings>" in user:
            return {"legitimate": {}, "clarity": 0.9, "notes": ""}
        if "<review_pass" in user:
            return {"summary": "", "findings": []}
        calls["n"] += 1
        # first evaluation = baseline (weak), second = candidate (strong)
        return {"summary": "s", "findings": full[:3] if calls["n"] == 1 else full}

    arbiter = StaticLLM(lambda s, u: {"decision": "replace", "rationale": "candidate finds far more planted defects", "absorbed_sections": [], "merged_body": None, "version_bump": "minor"})
    d = judge(cfg, StaticLLM(responder), arbiter, base, cand, trials_root)
    assert d.decision == "replace" and d.candidate_score > d.baseline_score
    assert d.resolved_version == "1.1.0" and "Extra section" in d.resolved_markdown
    resolved = parse_skill(d.resolved_markdown)
    assert resolved.phase == 4 and resolved.name == base.name


def test_judge_merge_is_validated_and_verified(cfg, skills_dir, trials_root):
    base = load_skills(skills_dir, cfg)[4]
    cand = _candidate_from(base)
    full = _gt_findings(trials_root, "04-development")
    review = _llm_for(full)
    merged_body = base.body + "\n\n## Absorbed\nCheck tenant identifiers too.\n"
    arbiter = StaticLLM(lambda s, u: {"decision": "merge", "rationale": "absorb one section", "absorbed_sections": ["tenant identifier check"], "merged_body": merged_body, "version_bump": "minor"})
    d = judge(cfg, review, arbiter, base, cand, trials_root)
    assert d.decision == "merge" and d.merged_eval is not None
    assert d.resolved_version == "1.1.0" and "## Absorbed" in d.resolved_markdown
    assert parse_skill(d.resolved_markdown).phase == 4

    # A merged body that fails validation (too short) falls back safely.
    bad_arbiter = StaticLLM(lambda s, u: {"decision": "merge", "rationale": "r", "absorbed_sections": [], "merged_body": "tiny", "version_bump": "minor"})
    d2 = judge(cfg, review, bad_arbiter, base, cand, trials_root)
    assert d2.decision == "keep_current" and any("failed validation" in g for g in d2.guards)


def test_judge_without_arbiter_uses_scores_only(cfg, skills_dir, trials_root):
    base = load_skills(skills_dir, cfg)[4]
    cand = _candidate_from(base)
    d = judge(cfg, _llm_for(_gt_findings(trials_root, "04-development")), None, base, cand, trials_root)
    assert d.decision == "keep_current" and any("judge model unavailable" in g for g in d.guards)


def test_apply_decision_writes_skill_and_credits(cfg, skills_dir, trials_root, tmp_path):
    base = load_skills(skills_dir, cfg)[4]
    cand = _candidate_from(base)
    full = _gt_findings(trials_root, "04-development")
    n = {"i": 0}

    def responder(system, user):
        if "<extra_findings>" in user:
            return {"legitimate": {}, "clarity": 0.9, "notes": ""}
        if "<review_pass" in user:
            return {"summary": "", "findings": []}
        n["i"] += 1
        return {"summary": "s", "findings": full[:2] if n["i"] == 1 else full}

    arbiter = StaticLLM(lambda s, u: {"decision": "replace", "rationale": "better", "absorbed_sections": [], "merged_body": None, "version_bump": "minor"})
    d = judge(cfg, StaticLLM(responder), arbiter, base, cand, trials_root)
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(cand.markdown, encoding="utf-8")
    credits = tmp_path / "CREDITS.md"
    changed = apply_decision(d, skill_path, credits, contributor="priya-dev", pr_number=42, pr_url="https://example/pr/42", phase_name="Development")
    assert parse_skill(skill_path.read_text(encoding="utf-8")).version == "1.1.0"
    text = credits.read_text(encoding="utf-8")
    assert "@priya-dev" in text and "replace" in text and "[#42](https://example/pr/42)" in text
    md = decision_markdown(d, "priya-dev", "Development")
    assert "replace" in md and "priya-dev" in md
    assert isinstance(changed, bool)


def test_bump_version():
    assert bump_version("1.2.3", "patch") == "1.2.4"
    assert bump_version("1.2.3", "minor") == "1.3.0"
    assert bump_version("1.2.3", "major") == "2.0.0"
