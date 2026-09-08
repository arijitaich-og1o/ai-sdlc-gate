"""Skip (waiver) requests: developers may skip phases with a recorded justification.

A skip is requested through commit-message trailers (or the same lines in a PR body):

    SDLC-Skip: 5
    SDLC-Skip-Reason: Test suite for the payment module is being rewritten in PAY-1432; this
                      commit only moves files and cannot be unit tested until then.

Rules enforced here (all configurable in gate.config.yaml):
- the reason must meet a minimum length;
- some phases require an approval label on the PR (default: deployment and maintenance);
- some finding categories (leaked secrets, etc.) can never be skipped;
- every skip, valid or not, is recorded in the metrics event.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Config


@dataclass
class SkipRequest:
    requested_phases: list[int] = field(default_factory=list)
    reason: str = ""
    valid_phases: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    approved_phases: list[int] = field(default_factory=list)

    @property
    def requested(self) -> bool:
        return bool(self.requested_phases) or bool(self.reason)

    @property
    def valid(self) -> bool:
        return self.requested and not self.errors and bool(self.valid_phases)

    def to_dict(self) -> dict:
        return {
            "requested": self.requested,
            "valid": self.valid,
            "requested_phases": self.requested_phases,
            "valid_phases": self.valid_phases,
            "approved_phases": self.approved_phases,
            "reason": self.reason,
            "errors": self.errors,
        }


def _trailer(text: str, key: str) -> list[str]:
    # Allow the reason to continue onto indented lines (RFC-822 style folding).
    pat = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*:[ \t]*(.*(?:\n[ \t]+.*)*)", re.I | re.M)
    return [" ".join(part.strip() for part in m.splitlines()).strip() for m in pat.findall(text)]


def parse_skip(cfg: Config, texts: list[str], approved_phases: list[int] | None = None) -> SkipRequest:
    sk = cfg.skip
    req = SkipRequest(approved_phases=sorted(set(approved_phases or [])))
    if not sk.get("enabled", True):
        return req
    phases_raw: list[str] = []
    reasons: list[str] = []
    for t in texts or []:
        phases_raw.extend(_trailer(t, sk["trailer_phases"]))
        reasons.extend(_trailer(t, sk["trailer_reason"]))
    if not phases_raw and not reasons:
        return req

    phases: set[int] = set()
    for raw in phases_raw:
        for token in re.split(r"[,\s;]+", raw.strip()):
            if not token:
                continue
            if token.lower() == "all":
                phases.update(cfg.phases.keys())
                continue
            if not token.isdigit() or int(token) not in cfg.phases:
                req.errors.append(f"invalid phase {token!r} in {sk['trailer_phases']} trailer")
                continue
            phases.add(int(token))
    req.requested_phases = sorted(phases)
    req.reason = " ".join(reasons).strip()

    if not req.requested_phases:
        req.errors.append(f"{sk['trailer_phases']} trailer did not name any valid phase")
    min_chars = int(sk.get("min_reason_chars", 40))
    if len(req.reason) < min_chars:
        req.errors.append(
            f"{sk['trailer_reason']} must be at least {min_chars} characters (got {len(req.reason)}); "
            "explain why the phase cannot be satisfied now and reference a ticket"
        )
    never = {int(p) for p in sk.get("never_skippable_phases") or []}
    needs_approval = {int(p) for p in sk.get("require_approval_for_phases") or []}
    approved = set(req.approved_phases)
    for p in req.requested_phases:
        if p in never:
            req.errors.append(f"phase {p} ({cfg.phase_name(p)}) can never be skipped")
            continue
        if p in needs_approval and p not in approved:
            req.errors.append(
                f"phase {p} ({cfg.phase_name(p)}) may only be skipped with the `{sk.get('approval_label')}` "
                "label applied by a code owner"
            )
            continue
        req.valid_phases.append(p)
    if req.errors:
        req.valid_phases = []
    return req
