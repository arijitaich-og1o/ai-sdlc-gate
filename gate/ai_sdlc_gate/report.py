"""Render gate reports as Markdown (PR comments, step summaries, terminal)."""
from __future__ import annotations

import textwrap

from .config import SEVERITIES, severity_rank
from .runner import GateReport

MARKER = "<!-- ai-sdlc-gate-report -->"
SEV_ICON = {"blocker": "🟥", "high": "🟧", "medium": "🟨", "low": "🟦", "info": "⬜"}
VERDICT_ICON = {"pass": "✅", "fail": "❌", "waived": "⚠️", "error": "💥"}


def _loc(f: dict) -> str:
    if not f.get("file"):
        return ""
    return f"`{f['file']}`" + (f":{f['line']}" if f.get("line") else "")


def _finding_line(f: dict) -> str:
    waived = " _(waived)_" if f.get("waived") else ""
    loc = _loc(f)
    head = f"- {SEV_ICON.get(f['severity'], '')} **{f['severity'].upper()}** `{f['category']}` {f['title']}{waived}"
    if loc:
        head += f" — {loc}"
    body = []
    if f.get("description"):
        body.append(f"  {f['description']}")
    if f.get("recommendation"):
        body.append(f"  **Fix:** {f['recommendation']}")
    return "\n".join([head, *body])


def to_markdown(report: GateReport, cfg=None, compact: bool = False) -> str:
    icon = VERDICT_ICON.get(report.verdict, "")
    lines: list[str] = [MARKER, f"## {icon} AI SDLC Gate: {report.verdict.upper()}", ""]
    it = report.intent
    lines.append(
        f"**Intent:** `{it.intent}` (detected via {it.source}) · **Phases checked:** "
        + ", ".join(f"{p}" for p in it.phases)
        + f" · **Blocking threshold:** `{report.threshold}`"
    )
    ctx = report.context or {}
    who = ctx.get("actor") or ctx.get("author_name") or ""
    if who:
        lines.append(f"**Developer:** @{who}" if ctx.get("actor") else f"**Developer:** {who}")
    st = report.stats or {}
    lines.append(f"**Change set:** {st.get('files', 0)} file(s), {st.get('commits', 0)} commit(s), {st.get('excluded', 0)} excluded as generated/binary")
    lines.append("")

    if report.fail_reasons:
        lines.append("### Why the gate failed")
        lines.extend(f"- {r}" for r in report.fail_reasons)
        lines.append("")

    lines.append("### Phase results")
    lines.append("| Phase | Skill | Verdict | 🟥 | 🟧 | 🟨 | 🟦 | ⬜ |")
    lines.append("|---|---|---|---|---|---|---|---|")
    if report.prechecks:
        c = {s: 0 for s in SEVERITIES}
        for f in report.prechecks:
            c[f["severity"]] += 1
        v = "fail" if any(severity_rank(f["severity"]) >= severity_rank(report.threshold) for f in report.prechecks) else "pass"
        lines.append(f"| pre-checks | secrets & credentials | {VERDICT_ICON[v]} {v} | {c['blocker']} | {c['high']} | {c['medium']} | {c['low']} | {c['info']} |")
    for p in report.phases:
        c = p.counts()
        lines.append(
            f"| {p.phase} · {p.phase_name} | {p.skill_name} v{p.skill_version} | {VERDICT_ICON.get(p.verdict, '')} {p.verdict} "
            f"| {c['blocker']} | {c['high']} | {c['medium']} | {c['low']} | {c['info']} |"
        )
    lines.append("")

    if report.skip.requested:
        lines.append("### Skip request")
        if report.skip.valid:
            lines.append(f"Phases **{', '.join(map(str, report.skip.valid_phases))}** were waived with justification:")
            lines.append(f"> {report.skip.reason}")
            lines.append("")
            lines.append("_Waived findings are still recorded in the organisation metrics._")
        else:
            lines.append("The skip request was **rejected**:")
            lines.extend(f"- {e}" for e in report.skip.errors)
        lines.append("")

    if not compact:
        if report.prechecks:
            lines.append("### Pre-check findings (never skippable)")
            lines.extend(_finding_line(f) for f in report.prechecks)
            lines.append("")
        for p in report.phases:
            if p.error:
                lines.append(f"### Phase {p.phase} · {p.phase_name}: review error")
                lines.append(f"```\n{p.error[:1500]}\n```")
                lines.append("")
                continue
            active = [f for f in p.findings if not f.get("waived")]
            waived = [f for f in p.findings if f.get("waived")]
            if not p.findings:
                continue
            lines.append(f"### Phase {p.phase} · {p.phase_name}")
            if p.summary:
                lines.append(f"_{p.summary}_")
                lines.append("")
            lines.extend(_finding_line(f) for f in active)
            if waived:
                lines.append("")
                lines.append("<details><summary>Waived findings</summary>")
                lines.append("")
                lines.extend(_finding_line(f) for f in waived)
                lines.append("")
                lines.append("</details>")
            lines.append("")

    lines.append("---")
    if report.verdict == "fail":
        lines.append(
            "**How to proceed:** fix the findings above and push again. If a phase genuinely cannot be satisfied "
            "right now, add the following trailers to your commit message (or PR description) and push again:"
        )
        lines.append("")
        lines.append("```")
        lines.append("SDLC-Skip: <phase numbers, e.g. 5>")
        lines.append("SDLC-Skip-Reason: <at least 40 characters explaining why, with a ticket reference>")
        lines.append("```")
        lines.append("")
        lines.append("Secrets, hard-coded credentials and known-vulnerable dependencies can never be skipped. "
                     "Skips of the deployment and maintenance phases are highlighted separately on the dashboard.")
    else:
        lines.append("_All required phases satisfied. Findings below the blocking threshold are advisory._")
    return "\n".join(lines)


def to_text(report: GateReport, full_report_path: str | None = None, max_findings: int = 25) -> str:
    """Compact rendering for terminals and hook output (no tables, no markup)."""
    thr = severity_rank(report.threshold)
    it = report.intent
    lines: list[str] = []
    verdict = "PASSED" if report.passed else "BLOCKED"
    lines.append(f"AI SDLC Gate: {verdict}")
    lines.append(f"Intent: {it.intent} · phases {', '.join(str(p) for p in it.phases)} · blocking threshold: {report.threshold}")
    if report.fail_reasons:
        lines.append("")
        lines.append("Why:")
        lines.extend(f"  - {r}" for r in report.fail_reasons)
    blocking = [f for f in report.all_findings() if severity_rank(f["severity"]) >= thr and not f.get("waived")]
    advisory = [f for f in report.all_findings() if f not in blocking]
    if blocking:
        lines.append("")
        lines.append("Findings that block this change:")
        for f in blocking[:max_findings]:
            loc = f"{f['file']}:{f['line']}" if f.get("file") and f.get("line") else (f.get("file") or "-")
            phase = f"phase {f['phase']}" if f.get("phase") else "pre-check"
            lines.append(f"  [{f['severity'].upper():7}] {loc}  ({phase}, {f['category']})")
            lines.append(f"            {f['title']}")
            if f.get("recommendation"):
                for w in textwrap.wrap("Fix: " + f["recommendation"], width=88):
                    lines.append(f"            {w}")
        if len(blocking) > max_findings:
            lines.append(f"  ... and {len(blocking) - max_findings} more blocking finding(s) in the full report")
    if advisory:
        lines.append("")
        lines.append(f"Advisory findings below the threshold: {len(advisory)} (see the full report)")
    if report.skip.requested:
        lines.append("")
        if report.skip.valid:
            lines.append(f"Skip applied for phase(s) {', '.join(map(str, report.skip.valid_phases))}: {report.skip.reason}")
        else:
            lines.append("Skip request rejected:")
            lines.extend(f"  - {e}" for e in report.skip.errors)
    for pr in report.phases:
        if pr.error:
            lines.append("")
            lines.append(f"Phase {pr.phase} ({pr.phase_name}) could not be reviewed: {pr.error[:300]}")
    lines.append("")
    if full_report_path:
        lines.append(f"Full report: {full_report_path}   (or run: ai-sdlc-gate last)")
    if not report.passed:
        lines.append("Fix the findings and commit again. To waive a phase that genuinely cannot be satisfied now, add to the commit message:")
        lines.append("  SDLC-Skip: <phase numbers>")
        lines.append("  SDLC-Skip-Reason: <at least 40 characters, with a ticket reference>")
        lines.append("Secrets, hard-coded credentials and known-vulnerable dependencies can never be waived.")
    return "\n".join(lines)
