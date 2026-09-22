"""Command line interface for the AI SDLC Gate."""
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
from . import identity as identity_mod
from . import ledger as ledger_mod
from . import ghauth
from . import keybroker
from . import llm as llm_mod
from . import secrets_store
from .intent import detect_intent
from .judge import apply_decision, decision_markdown, judge
from .llm import LLMClient, LLMError, StaticLLM
from .prechecks import run_prechecks
from .report import to_markdown, to_text
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


def _judge_llm(cfg: Config, offline: bool) -> Any | None:
    return None if offline else LLMClient.from_config(cfg, model="judge")


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
    ledger = None
    ledger_file = None
    use_ledger = bool((cfg.gate.get("review") or {}).get("ledger", True)) and not args.no_ledger and not os.environ.get("GITHUB_ACTIONS")
    if use_ledger:
        ledger_file = ledger_mod.ledger_path(context["repo"] or str(root), context["ref"] or cs.branch)
        ledger = ledger_mod.Ledger.load(ledger_file)
        ledger.repo, ledger.branch = context["repo"] or str(root), context["ref"] or cs.branch
    try:
        report = run_gate(cfg, llm, skills, cs, intent, skip, fail_on=args.fail_on, context=context, ledger=ledger)
    finally:
        llm.close()
    if ledger is not None and ledger_file is not None:
        ledger.save(ledger_file)

    md = to_markdown(report, cfg)
    _write(args.output_md, md)
    _write(args.output_json, json.dumps(report.to_dict(), indent=2))
    if args.output_text:
        _write(args.output_text, to_text(report, full_report_path=args.output_md))
    if not args.quiet:
        print(to_text(report, full_report_path=args.output_md) if args.text else md)
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
        judge_llm = _judge_llm(cfg, args.offline)
    except LLMError as exc:
        _eprint(f"LLM configuration error: {exc}")
        return EXIT_ERROR
    ev = evaluate_skill(cfg, llm, skill, Path(args.trials), judge_llm)
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
        judge_llm = _judge_llm(cfg, args.offline)
    except LLMError as exc:
        _eprint(f"LLM configuration error: {exc}")
        return EXIT_ERROR
    try:
        decision = judge(cfg, review_llm, judge_llm, baseline, candidate, Path(args.trials))
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
    cred = ghauth.find_credential(token_env=args.token_env) if args.dispatch else None
    if cred and cred.username and not report.context.get("actor"):
        report.context["actor"] = cred.username
    event = metrics_mod.build_event(report)
    _write(args.output, json.dumps(event, indent=2))
    if args.dispatch:
        cfg = Config.load(args.config)
        repo = args.repo or cfg.metrics["central_repo"]
        if cred is None:
            _eprint("metrics: no GitHub credential found (gh auth login, or push once so the git credential helper stores one); run not recorded")
            return EXIT_FAIL
        try:
            metrics_mod.dispatch_event(event, repo, cred.token, cfg.metrics["dispatch_event"])
        except (ValueError, RuntimeError) as exc:
            _eprint(f"metrics dispatch failed: {exc}")
            return EXIT_FAIL
        print(f"metrics event {event['id']} recorded ({cred.source})")
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
    p = argparse.ArgumentParser(prog="ai-sdlc-gate", description="AI SDLC standardization gate (Otto Group One.O India)")
    p.add_argument("--version", action="version", version=f"ai-sdlc-gate {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser, skills: bool = True) -> None:
        sp.add_argument("--config", help="path to gate.config.yaml (default: $AI_SDLC_GATE_CONFIG or ./gate.config.yaml)")
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
    r.add_argument("--output-json"), r.add_argument("--output-md"), r.add_argument("--output-text", help="write the compact terminal rendering here")
    r.add_argument("--text", action="store_true", help="print the compact terminal rendering instead of markdown")
    r.add_argument("--no-ledger", action="store_true", help="do not use the per-repository memory of previous runs")
    r.add_argument("--offline", action="store_true", help="do not call the model (pre-checks only; for tests)")
    r.add_argument("--quiet", action="store_true")
    r.set_defaults(func=cmd_run)

    last = sub.add_parser("last", help="show the result of the last gate run on this machine")
    last.add_argument("--md", action="store_true", help="show the full markdown report")
    last.add_argument("--json", action="store_true", help="show the raw JSON report")
    last.set_defaults(func=cmd_last)

    i = sub.add_parser("intent", help="show the detected intent and phases for a change set")
    common(i, skills=False)
    i.add_argument("--staged", action="store_true")
    i.add_argument("--base"), i.add_argument("--head"), i.add_argument("--intent"), i.add_argument("--ref")
    i.set_defaults(func=cmd_intent)

    v = sub.add_parser("validate-skills", help="verify the repository holds exactly 8 valid phase skills")
    common(v)
    v.set_defaults(func=cmd_validate_skills)

    pc = sub.add_parser("precheck", help="run deterministic secret/credential checks on paths")
    common(pc, skills=False)
    pc.add_argument("--paths", nargs="+")
    pc.set_defaults(func=cmd_precheck)

    e = sub.add_parser("evaluate", help="score one skill against the trials")
    common(e, skills=False)
    e.add_argument("--skill", required=True), e.add_argument("--trials", required=True), e.add_argument("--phase")
    e.add_argument("--output"), e.add_argument("--offline", action="store_true")
    e.set_defaults(func=cmd_evaluate)

    c = sub.add_parser("challenge", help="arbitrate between the current skill and a candidate")
    common(c, skills=False)
    c.add_argument("--baseline", required=True, help="path to the current SKILL.md (from the base branch)")
    c.add_argument("--candidate", required=True, help="path to the proposed SKILL.md")
    c.add_argument("--trials", required=True)
    c.add_argument("--skill-path", help="where to write the resolved skill (usually the candidate path)")
    c.add_argument("--credits", help="CREDITS.md to update")
    c.add_argument("--contributor"), c.add_argument("--pr-number"), c.add_argument("--pr-url")
    c.add_argument("--output-json"), c.add_argument("--output-md")
    c.add_argument("--offline", action="store_true")
    c.set_defaults(func=cmd_challenge)

    m = sub.add_parser("emit-metrics", help="build (and optionally dispatch) a metrics event from a report")
    m.add_argument("--config")
    m.add_argument("--report", required=True), m.add_argument("--output")
    m.add_argument("--dispatch", action="store_true"), m.add_argument("--repo"), m.add_argument("--token-env", default="AI_SDLC_GATE_TOKEN")
    m.set_defaults(func=cmd_emit_metrics)

    mm = sub.add_parser("metrics", help="metrics store operations")
    msub = mm.add_subparsers(dest="mcmd", required=True)
    mi = msub.add_parser("ingest")
    mi.add_argument("--payload", required=True), mi.add_argument("--events-dir", required=True)
    mi.set_defaults(func=cmd_metrics_ingest)
    mb = msub.add_parser("build")
    mb.add_argument("--events-dir", required=True), mb.add_argument("--out", required=True)
    mb.set_defaults(func=cmd_metrics_build)
    _add_client_parsers(sub)
    return p


# ----------------------------------------------------------------------------- identity / client

EXIT_IDENTITY_REQUIRED = 3


def _identity_configured(idc: dict) -> bool:
    return bool(str(idc.get("tenant") or "").strip()) and bool(str(idc.get("client_id") or "").strip())


def cmd_identity(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    idc = cfg.identity
    if args.icmd == "show":
        ident = identity_mod.load_identity()
        if ident is None or ident.expired:
            if not args.quiet:
                _eprint("no verified identity; run `ai-sdlc-gate identity login`")
            return EXIT_IDENTITY_REQUIRED
        if args.quiet:
            print(ident.email)
        else:
            print(json.dumps(ident.to_dict(), indent=2))
        return EXIT_PASS
    if args.icmd == "logout":
        print("identity removed" if identity_mod.clear_identity() else "no identity stored")
        return EXIT_PASS
    if args.icmd == "check":
        # Exit 0 when a valid identity exists, or when the identity provider is not configured yet (nothing to
        # require). Exit 3 when the policy requires an identity and none is present.
        ident = identity_mod.load_identity()
        if ident is not None and not ident.expired:
            print(ident.email)
            return EXIT_PASS
        if not _identity_configured(idc):
            print("identity provider not configured; identity not required")
            return EXIT_PASS
        if not idc.get("required", False) and not args.strict:
            print("identity optional by policy")
            return EXIT_PASS
        _eprint("A verified identity is required before committing. Run: ai-sdlc-gate identity login")
        return EXIT_IDENTITY_REQUIRED
    tenant = args.tenant or os.environ.get("AI_SDLC_GATE_ENTRA_TENANT") or idc.get("tenant", "")
    client_id = args.client_id or os.environ.get("AI_SDLC_GATE_ENTRA_CLIENT_ID") or idc.get("client_id", "")
    if not tenant or not client_id:
        _eprint("identity: the Microsoft Entra application is not configured yet (identity.tenant / identity.client_id in gate.config.yaml); "
                "sign-in will be enabled by the platform team. Nothing to do now.")
        return EXIT_PASS
    domains = list(idc.get("allowed_domains") or [])
    authority = idc.get("authority") or identity_mod.DEFAULT_AUTHORITY
    try:
        if args.device_code:
            ident = identity_mod.device_code_login(tenant, client_id, allowed_domains=domains, authority=authority, open_browser=not args.no_browser)
        else:
            try:
                ident = identity_mod.browser_login(tenant, client_id, allowed_domains=domains, authority=authority,
                                                   browser=(lambda u: False) if args.no_browser else identity_mod.open_url)
            except identity_mod.IdentityError as exc:
                if "timed out" in str(exc) or args.no_browser:
                    raise
                _eprint(f"identity: browser sign-in did not complete ({exc}); trying the device-code sign-in instead")
                ident = identity_mod.device_code_login(tenant, client_id, allowed_domains=domains, authority=authority, open_browser=not args.no_browser)
    except identity_mod.IdentityError as exc:
        _eprint(f"identity: {exc}")
        if "53003" in str(exc) or "AADSTS53003" in str(exc) or "does not meet the criteria" in str(exc):
            _eprint("Your organisation's Conditional Access policy blocks this sign-in application. The platform team must register a dedicated "
                    "'AI SDLC Gate client' application and put its tenant and client id into gate.config.yaml (see docs/enforcement.md).")
        return EXIT_FAIL
    path = identity_mod.save_identity(ident)
    if not args.no_git:
        identity_mod.configure_git_identity(ident)
    print(f"Signed in as {ident.email}. Your commits will carry this identity.", flush=True)
    return EXIT_PASS


def cmd_attest(args: argparse.Namespace) -> int:
    """Stamp a commit message with the local gate attestation (called by the commit-msg hook)."""
    cfg = Config.load(args.config)
    ident = identity_mod.load_identity()
    if ident is not None and ident.expired:
        ident = None
    required = (bool(cfg.identity.get("required")) or args.require_identity) and _identity_configured(cfg.identity)
    if required and ident is None:
        _eprint("A verified identity is required before committing. Run: ai-sdlc-gate identity login")
        return EXIT_IDENTITY_REQUIRED
    line = identity_mod.attestation_line(args.result, __version__, ident)
    added = identity_mod.append_attestation(Path(args.message_file), line)
    if not args.quiet:
        print(line if added else "attestation already present")
    return EXIT_PASS


def cmd_configure(args: argparse.Namespace) -> int:
    """Obtain the model-gateway configuration and keep it in the operating system credential store.

    By default it is fetched from the central repository through the key-broker workflow, using the developer's
    existing GitHub credential. `--api-key`/`--base-url` store explicit values instead (platform use).
    `--check` only reports whether a configuration is available; `--clear` removes it.
    """
    cfg = Config.load(args.config)
    if args.check:
        stored = secrets_store.load()
        if stored is None or not stored.base_url:
            _eprint("the review engine is not set up on this machine; run: ai-sdlc-gate configure")
            return EXIT_FAIL
        print("review engine ready")
        return EXIT_PASS
    if args.clear:
        secrets_store.clear()
        print("review engine configuration removed")
        return EXIT_PASS
    if args.export_record:
        stored = secrets_store.load()
        if stored is None:
            _eprint("the review engine is not set up on this machine")
            return EXIT_FAIL
        print(stored.to_json(), flush=True)
        return EXIT_PASS
    if args.import_record:
        raw = sys.stdin.read()
        rec = secrets_store.Stored.from_json(raw, "import")
        if rec is None or not rec.base_url:
            _eprint("no valid record on standard input")
            return EXIT_FAIL
        try:
            llm_mod.validate_base_url(rec.base_url)
        except llm_mod.LLMError as exc:
            _eprint(f"configure: refusing to store the record: {exc}")
            return EXIT_FAIL
        secrets_store.store(rec.base_url, rec.api_key, models=rec.models, mode=rec.mode)
        print("Review engine ready.", flush=True)
        return EXIT_PASS
    if args.api_key:
        if not args.base_url:
            _eprint("--base-url is required together with --api-key")
            return EXIT_FAIL
        try:
            llm_mod.validate_base_url(args.base_url)
        except llm_mod.LLMError as exc:
            _eprint(f"configure: {exc}")
            return EXIT_FAIL
        models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
        st = secrets_store.store(args.base_url, args.api_key, models=models, mode="manual")
        print("Review engine ready.")
        return EXIT_PASS
    cred = ghauth.find_credential(token_env="AI_SDLC_GATE_GITHUB_TOKEN")
    if cred is None:
        _eprint(
            "No GitHub credential found. Sign in once with `gh auth login`, or push/pull any repository so the git credential "
            "helper stores your credential, then run `ai-sdlc-gate configure` again."
        )
        return EXIT_FAIL
    repo = args.repo or cfg.metrics["central_repo"]
    try:
        llm = keybroker.fetch_config(cred.token, repo, ref=args.ref or "main", out=lambda m: print(f"[ai-sdlc-gate] {m}", flush=True))
    except keybroker.KeyBrokerError as exc:
        _eprint(f"configure: {exc}")
        return EXIT_FAIL
    if not llm.base_url:
        _eprint("configure: the central repository is not fully configured (contact the platform team)")
        return EXIT_FAIL
    problem = _verify_litellm_key(llm.base_url, llm.api_key)
    if problem:
        _eprint(f"configure: the review engine could not be verified: {problem}")
        _eprint("Ask the platform team to check the central repository configuration, then run `ai-sdlc-gate configure` again.")
        return EXIT_FAIL
    st = secrets_store.store(llm.base_url, llm.api_key, models=llm.models or [], mode=llm.mode)
    if st.backend != "keyring":
        _eprint("note: no operating system credential store is available on this machine; an encrypted file is used instead")
    print("Review engine ready.", flush=True)
    return EXIT_PASS


def _verify_litellm_key(base_url: str, api_key: str) -> str | None:
    """Return a human-readable problem description, or None when the key works."""
    import httpx

    if not api_key.startswith("sk-"):
        return "the API key must start with 'sk-' (the secret includes a label or prefix)"
    url = base_url.rstrip("/")
    url = f"{url}/models" if url.endswith("/v1") else f"{url}/v1/models"
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    except httpx.HTTPError as exc:
        return f"could not reach the gateway: {type(exc).__name__}"
    if resp.status_code in (401, 403):
        return f"the gateway rejected the key (HTTP {resp.status_code})"
    if resp.status_code >= 400:
        return f"the gateway returned HTTP {resp.status_code}"
    return None


def _add_client_parsers(sub: argparse._SubParsersAction) -> None:
    idp = sub.add_parser("identity", help="verified developer identity (Microsoft Entra ID)")
    idp.add_argument("--config")
    isub = idp.add_subparsers(dest="icmd", required=True)
    login = isub.add_parser("login", help="sign in with the device-code flow and store the verified e-mail")
    login.add_argument("--tenant"), login.add_argument("--client-id")
    login.add_argument("--device-code", action="store_true", help="use the device-code sign-in (for SSH/headless machines) instead of the browser sign-in")
    login.add_argument("--no-browser", action="store_true", help="do not try to open a browser"), login.add_argument("--no-git", action="store_true", help="do not update git user.email/user.name")
    show = isub.add_parser("show")
    show.add_argument("--quiet", action="store_true", help="print only the e-mail; exit 3 when absent")
    check = isub.add_parser("check", help="exit 0 if an identity exists or none is required yet; 3 if one is required and missing")
    check.add_argument("--strict", action="store_true", help="require an identity whenever the provider is configured (managed mode)")
    logout = isub.add_parser("logout")
    for sp in (login, show, check, logout):
        sp.add_argument("--config")
    idp.set_defaults(func=cmd_identity)

    at = sub.add_parser("attest", help="append the AI-SDLC-Gate-Client trailer to a commit message (hook use)")
    at.add_argument("--config"), at.add_argument("--message-file", required=True)
    at.add_argument("--result", choices=["pass", "waived"], default="pass")
    at.add_argument("--require-identity", action="store_true"), at.add_argument("--quiet", action="store_true")
    at.set_defaults(func=cmd_attest)

    cf = sub.add_parser("configure", help="prepare the review engine on this machine (uses your GitHub sign-in)")
    cf.add_argument("--config"), cf.add_argument("--base-url"), cf.add_argument("--api-key", help="store this key instead of using the key broker (with --base-url)")
    cf.add_argument("--models", help="comma separated model names to store with --api-key")
    cf.add_argument("--repo", help="central repository (default from policy)"), cf.add_argument("--ref", help="branch of the central repository (default main)")
    cf.add_argument("--check", action="store_true", help="exit 0 if the review engine is set up, 1 otherwise")
    cf.add_argument("--clear", action="store_true", help="remove the review engine configuration")
    cf.add_argument("--export-record", action="store_true", help=argparse.SUPPRESS)
    cf.add_argument("--import-record", action="store_true", help=argparse.SUPPRESS)
    cf.set_defaults(func=cmd_configure)

    up = sub.add_parser("update", help="refresh policy, skills and engine on this machine now")
    up.set_defaults(func=cmd_update)


def cmd_update(args: argparse.Namespace) -> int:
    """Refresh policy, skills and engine now (the hooks do this at most once a day)."""
    import platform
    import subprocess

    home = identity_mod.sdlc_home()
    repo = home / "repo"
    if not (repo / ".git").is_dir():
        _eprint(f"no installation found at {home}; run the installer")
        return EXIT_FAIL
    origin = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    ref = (home / "ref").read_text(encoding="utf-8").strip() if (home / "ref").is_file() else "main"
    # Inside WSL the source is the Windows copy; refresh that first with Windows git (which holds the GitHub sign-in).
    local = origin[7:] if origin.startswith("file://") else origin
    if identity_mod.is_wsl() and local.startswith("/mnt/"):
        drive = local[5]
        win_path = f"{drive.upper()}:" + local[6:].replace("/", "\\")
        for exe in ("git.exe", "/mnt/c/Program Files/Git/cmd/git.exe"):
            r = subprocess.run([exe, "-C", win_path, "pull", "--ff-only", "--quiet"], capture_output=True, text=True)
            if r.returncode == 0:
                print("[ai-sdlc-gate] refreshed the Windows copy", flush=True)
                break
    env = {**os.environ, "AI_SDLC_GATE_NONINTERACTIVE": "1", "AI_SDLC_GATE_REPO_URL": origin, "AI_SDLC_GATE_REF": ref}
    if platform.system() == "Windows":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(repo / "client" / "install.ps1")]
    else:
        cmd = ["bash", str(repo / "client" / "install.sh")]
    return subprocess.run(cmd, env=env).returncode


def cmd_last(args: argparse.Namespace) -> int:
    home = identity_mod.sdlc_home()
    name = "last-report.json" if args.json else ("last-report.md" if args.md else "last-report.txt")
    path = home / name
    if not path.is_file():
        _eprint("no gate run recorded on this machine yet")
        return EXIT_FAIL
    print(path.read_text(encoding="utf-8"), flush=True)
    return EXIT_PASS


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
