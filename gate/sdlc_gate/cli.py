"""Command line interface for the SDLC Gate."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import metrics as metrics_mod
from .changes import collect_paths, collect_range, collect_staged
from .config import Config
from .evaluate import evaluate_skill
from .gitutil import GitError, repo_root
from .intent import detect_intent
from .judge import apply_decision, decision_markdown, judge
from .llm import LLMClient, LLMError, StaticLLM
from .prechecks import run_prechecks
from .report import to_markdown
from .runner import run_gate
from .skills import load_skill_file, load_skills, validate_skills_dir
from .skip import parse_skip

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


def _eprint(*a: Any) -> None:
    print(*a, file=sys.stderr, flush=True)


def _write(path: str | None, text: str) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8", newline="\n")


def _default_root() -> Path:
    try:
        return repo_root()
    except GitError:
        return Path.cwd()


def _skills_dir(args: argparse.Namespace, cfg: Config) -> Path:
    if getattr(args, "skills_dir", None):
        return Path(args.skills_dir)
    if cfg.source is not None:
        return cfg.source.parent / "skills"
    return _default_root() / "skills"


def _make_llm(cfg: Config, offline: bool, model: str | None = None) -> Any:
    if offline:
        return StaticLLM()
    return LLMClient.from_config(cfg, model=model)


def _parse_phases(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok))
    return out


# ----------------------------------------------------------------------------- run

def cmd_run(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    root = Path(args.root).resolve() if args.root else _default_root()
    try:
        skills = load_skills(_skills_dir(args, cfg), cfg)
    except ValueError as exc:
        _eprint(str(exc))
        return EXIT_ERROR

    try:
        if args.staged:
            cs = collect_staged(cfg, root)
        elif args.paths:
            cs = collect_paths(cfg, args.paths, root)
        else:
            head = args.head or "HEAD"
            cs = collect_range(cfg, args.base, head, root)
    except GitError as exc:
        _eprint(f"git error: {exc}")
        return EXIT_ERROR

    texts = list(cs.commit_messages)
    if args.pr_body_file and Path(args.pr_body_file).is_file():
        texts.append(Path(args.pr_body_file).read_text(encoding="utf-8", errors="replace"))
    try:
        intent = detect_intent(cfg, explicit=args.intent or None, commit_messages=texts, branch=args.ref or cs.branch, paths=cs.paths)
    except ValueError as exc:
        _eprint(str(exc))
        return EXIT_ERROR
    skip = parse_skip(cfg, texts, approved_phases=_parse_phases(args.approved_skip_phases))

    context = {
        "repo": args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        "actor": args.actor or os.environ.get("GITHUB_ACTOR", ""),
        "ref": args.ref or os.environ.get("GITHUB_REF_NAME", cs.branch),
        "sha": args.sha or os.environ.get("GITHUB_SHA", cs.head),
        "run_id": args.run_id or os.environ.get("GITHUB_RUN_ID", ""),
        "run_url": args.run_url or "",
        "event_name": args.event_name or os.environ.get("GITHUB_EVENT_NAME", "local"),
        "pr_number": int(args.pr_number) if args.pr_number and str(args.pr_number).isdigit() else None,
    }

    try:
        llm = _make_llm(cfg, args.offline)
    except LLMError as exc:
        _eprint(f"LLM configuration error: {exc}")
        return EXIT_ERROR
    try:
        report = run_gate(cfg, llm, skills, cs, intent, skip, fail_on=args.fail_on, context=context)
    finally:
        llm.close()

    md = to_markdown(report, cfg)
    _write(args.output_md, md)
    _write(args.output_json, json.dumps(report.to_dict(), indent=2))
    if not args.quiet:
        print(md)
    return EXIT_PASS if report.passed else EXIT_FAIL


# ----------------------------------------------------------------------------- intent

def cmd_intent(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    root = Path(args.root).resolve() if args.root else _default_root()
    messages: list[str] = []
    paths: list[str] = []
    branch = args.ref
    try:
        if args.staged:
            cs = collect_staged(cfg, root)
        elif args.base or args.head:
            cs = collect_range(cfg, args.base, args.head or "HEAD", root)
        else:
            cs = None
        if cs is not None:
            messages, paths, branch = cs.commit_messages, cs.paths, branch or cs.branch
    except GitError as exc:
        _eprint(f"git error: {exc}")
        return EXIT_ERROR
    try:
        d = detect_intent(cfg, explicit=args.intent or None, commit_messages=messages, branch=branch, paths=paths)
    except ValueError as exc:
        _eprint(str(exc))
        return EXIT_ERROR
    print(json.dumps(d.to_dict(), indent=2))
    return EXIT_PASS


# ----------------------------------------------------------------------------- validate

def cmd_validate_skills(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    skills, errors = validate_skills_dir(_skills_dir(args, cfg), cfg)
    if errors:
        _eprint("Skill validation FAILED:")
        for e in errors:
            _eprint(f"  - {e}")
        return EXIT_FAIL
    for p in sorted(skills):
        s = skills[p]
        print(f"phase {p}: {s.slug:<16} {s.name} v{s.version}")
    print(f"OK: exactly {len(skills)} skills, one per SDLC phase")
    return EXIT_PASS


# ----------------------------------------------------------------------------- precheck

def cmd_precheck(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    root = Path(args.root).resolve() if args.root else _default_root()
    cs = collect_paths(cfg, args.paths or ["."], root)
    findings = run_prechecks(cfg, cs)
    for f in findings:
        loc = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        print(f"[{f['severity']}] {f['title']} — {loc}")
    if findings:
        _eprint(f"{len(findings)} pre-check finding(s)")
        return EXIT_FAIL
    print(f"pre-checks clean ({len(cs.files)} files scanned)")
    return EXIT_PASS


# ----------------------------------------------------------------------------- evaluate

def cmd_evaluate(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    skill = load_skill_file(Path(args.skill))
    if args.phase and int(args.phase) != skill.phase:
        _eprint(f"skill declares phase {skill.phase} but --phase {args.phase} was given")
        return EXIT_ERROR
    try:
        llm = _make_llm(cfg, args.offline)
        judge_llm = None if args.offline else _make_llm(cfg, False, model=os.environ.get("SDLC_JUDGE_MODEL") or cfg.llm["judge_model"])
    except LLMError as exc:
        _eprint(f"LLM configuration error: {exc}")
        return EXIT_ERROR
    ev = evaluate_skill(cfg, llm, skill, Path(args.demo), judge_llm)
    out = json.dumps(ev.to_dict(), indent=2)
    _write(args.output, out)
    print(out)
    return EXIT_PASS if not ev.error else EXIT_ERROR


# ----------------------------------------------------------------------------- challenge

def cmd_challenge(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    baseline = load_skill_file(Path(args.baseline)) if Path(args.baseline).is_file() else None
    try:
        candidate = load_skill_file(Path(args.candidate))
    except ValueError as exc:
        _eprint(f"candidate skill is invalid: {exc}")
        return EXIT_FAIL
    if baseline is None:
        _eprint("baseline skill not found; challenges require an existing skill for the phase")
        return EXIT_ERROR
    candidate.slug = baseline.slug
    try:
        review_llm = _make_llm(cfg, args.offline)
        judge_llm = None if args.offline else _make_llm(cfg, False, model=os.environ.get("SDLC_JUDGE_MODEL") or cfg.llm["judge_model"])
    except LLMError as exc:
        _eprint(f"LLM configuration error: {exc}")
        return EXIT_ERROR
    try:
        decision = judge(cfg, review_llm, judge_llm, baseline, candidate, Path(args.demo))
    finally:
        review_llm.close()
        if judge_llm:
            judge_llm.close()
    phase_name = cfg.phase_name(decision.phase)
    changed = False
    if args.skill_path:
        changed = apply_decision(
            decision,
            Path(args.skill_path),
            Path(args.credits) if args.credits else None,
            contributor=args.contributor or "unknown",
            pr_number=args.pr_number,
            pr_url=args.pr_url,
            phase_name=phase_name,
        )
    md = decision_markdown(decision, args.contributor or "unknown", phase_name)
    _write(args.output_md, md)
    _write(args.output_json, json.dumps({**decision.to_dict(), "skill_file_changed": changed}, indent=2))
    print(md)
    return EXIT_PASS


# ----------------------------------------------------------------------------- metrics

def cmd_emit_metrics(args: argparse.Namespace) -> int:
    from .intent import IntentDecision
    from .runner import GateReport, PhaseResult
    from .skip import SkipRequest

    data = json.loads(Path(args.report).read_text(encoding="utf-8"))
    intent = IntentDecision(**{k: data["intent"][k] for k in ("intent", "phases", "source", "notes")})
    skip = SkipRequest(
        requested_phases=data["skip"].get("requested_phases", []),
        reason=data["skip"].get("reason", ""),
        valid_phases=data["skip"].get("valid_phases", []),
        errors=data["skip"].get("errors", []),
        approved_phases=data["skip"].get("approved_phases", []),
    )
    phases = []
    for p in data["phases"]:
        pr = PhaseResult(
            phase=p["phase"], phase_name=p["phase_name"], skill_name=p["skill_name"], skill_version=p["skill_version"],
            findings=p.get("findings", []), summary=p.get("summary", ""), verdict=p["verdict"], waived=p.get("waived", False),
            error=p.get("error"), model=p.get("model", ""), duration_s=float(p.get("duration_s", 0)), chunks=int(p.get("chunks", 1)),
        )
        phases.append(pr)
    report = GateReport(
        intent=intent, phases=phases, prechecks=data.get("prechecks", []), skip=skip, verdict=data["verdict"],
        fail_reasons=data.get("fail_reasons", []), threshold=data.get("threshold", "high"), stats=data.get("stats", {}),
        context=data.get("context", {}), llm_usage=data.get("llm_usage", {}), generated_at=data.get("generated_at"),
    )
    event = metrics_mod.build_event(report)
    _write(args.output, json.dumps(event, indent=2))
    if args.dispatch:
        cfg = Config.load(args.config)
        repo = args.repo or cfg.metrics["central_repo"]
        token = os.environ.get(args.token_env, "")
        try:
            metrics_mod.dispatch_event(event, repo, token, cfg.metrics["dispatch_event"])
        except (ValueError, RuntimeError) as exc:
            _eprint(f"metrics dispatch failed: {exc}")
            return EXIT_FAIL
        print(f"metrics event {event['id']} dispatched to {repo}")
    else:
        print(json.dumps(event, indent=2))
    return EXIT_PASS


def cmd_metrics_ingest(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    event = payload.get("event", payload) if isinstance(payload, dict) else payload
    try:
        path, written = metrics_mod.ingest_event(event, Path(args.events_dir))
    except ValueError as exc:
        _eprint(str(exc))
        return EXIT_FAIL
    print(f"{'stored' if written else 'duplicate, skipped'}: {path}")
    return EXIT_PASS


def cmd_metrics_build(args: argparse.Namespace) -> int:
    summary = metrics_mod.build_dashboard(Path(args.events_dir), Path(args.out))
    org = summary["organisation"]
    print(f"dashboard built from {summary['events']} events: runs={org['runs']} pass_rate={org['pass_rate']} blocked={org['blocked']} skips_granted={org['skips_granted']}")
    return EXIT_PASS


# ----------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdlc-gate", description="AI SDLC standardization gate (Otto Group One.O India)")
    p.add_argument("--version", action="version", version=f"sdlc-gate {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser, skills: bool = True) -> None:
        sp.add_argument("--config", help="path to gate.config.yaml (default: $SDLC_GATE_CONFIG or ./gate.config.yaml)")
        sp.add_argument("--root", help="repository root to operate in (default: current git repo)")
        if skills:
            sp.add_argument("--skills-dir", help="directory holding the 7 phase skills (default: next to the config)")

    r = sub.add_parser("run", help="review a change set through the SDLC phase gates")
    common(r)
    src = r.add_mutually_exclusive_group()
    src.add_argument("--staged", action="store_true", help="review the staged index (pre-commit hook)")
    src.add_argument("--paths", nargs="+", help="review whole files/directories instead of a git range")
    r.add_argument("--base", help="base revision (exclusive); defaults to HEAD~1")
    r.add_argument("--head", help="head revision (default HEAD)")
    r.add_argument("--intent", help="explicit intent (plan|design|commit|push|pr|release|deploy|hotfix|maintenance)")
    r.add_argument("--fail-on", help="blocking severity threshold override (blocker|high|medium|low)")
    r.add_argument("--pr-body-file", help="file containing the pull request body (for trailers)")
    r.add_argument("--approved-skip-phases", help="comma separated phases whose skip has been approved via label")
    r.add_argument("--repo"), r.add_argument("--actor"), r.add_argument("--ref"), r.add_argument("--sha")
    r.add_argument("--run-id"), r.add_argument("--run-url"), r.add_argument("--event-name"), r.add_argument("--pr-number")
    r.add_argument("--output-json"), r.add_argument("--output-md")
    r.add_argument("--offline", action="store_true", help="do not call the model (pre-checks only; for tests)")
    r.add_argument("--quiet", action="store_true")
    r.set_defaults(func=cmd_run)

    i = sub.add_parser("intent", help="show the detected intent and phases for a change set")
    common(i, skills=False)
    i.add_argument("--staged", action="store_true")
    i.add_argument("--base"), i.add_argument("--head"), i.add_argument("--intent"), i.add_argument("--ref")
    i.set_defaults(func=cmd_intent)

    v = sub.add_parser("validate-skills", help="verify the repository holds exactly 7 valid phase skills")
    common(v)
    v.set_defaults(func=cmd_validate_skills)

    pc = sub.add_parser("precheck", help="run deterministic secret/credential checks on paths")
    common(pc, skills=False)
    pc.add_argument("--paths", nargs="+")
    pc.set_defaults(func=cmd_precheck)

    e = sub.add_parser("evaluate", help="score one skill against the demo codebase")
    common(e, skills=False)
    e.add_argument("--skill", required=True), e.add_argument("--demo", required=True), e.add_argument("--phase")
    e.add_argument("--output"), e.add_argument("--offline", action="store_true")
    e.set_defaults(func=cmd_evaluate)

    c = sub.add_parser("challenge", help="arbitrate between the current skill and a candidate")
    common(c, skills=False)
    c.add_argument("--baseline", required=True, help="path to the current SKILL.md (from the base branch)")
    c.add_argument("--candidate", required=True, help="path to the proposed SKILL.md")
    c.add_argument("--demo", required=True)
    c.add_argument("--skill-path", help="where to write the resolved skill (usually the candidate path)")
    c.add_argument("--credits", help="CREDITS.md to update")
    c.add_argument("--contributor"), c.add_argument("--pr-number"), c.add_argument("--pr-url")
    c.add_argument("--output-json"), c.add_argument("--output-md")
    c.add_argument("--offline", action="store_true")
    c.set_defaults(func=cmd_challenge)

    m = sub.add_parser("emit-metrics", help="build (and optionally dispatch) a metrics event from a report")
    m.add_argument("--config")
    m.add_argument("--report", required=True), m.add_argument("--output")
    m.add_argument("--dispatch", action="store_true"), m.add_argument("--repo"), m.add_argument("--token-env", default="SDLC_GATE_TOKEN")
    m.set_defaults(func=cmd_emit_metrics)

    mm = sub.add_parser("metrics", help="metrics store operations")
    msub = mm.add_subparsers(dest="mcmd", required=True)
    mi = msub.add_parser("ingest")
    mi.add_argument("--payload", required=True), mi.add_argument("--events-dir", required=True)
    mi.set_defaults(func=cmd_metrics_ingest)
    mb = msub.add_parser("build")
    mb.add_argument("--events-dir", required=True), mb.add_argument("--out", required=True)
    mb.set_defaults(func=cmd_metrics_build)
    return p


def _utf8_console() -> None:
    """Reports contain non-ASCII symbols; make sure Windows consoles do not choke on them."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return EXIT_ERROR
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _eprint(f"error: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
