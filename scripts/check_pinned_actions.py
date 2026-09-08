#!/usr/bin/env python3
"""Workflow hygiene checks for this repository.

- every `uses:` of a third-party action is pinned to a full 40-hex commit SHA (docker images to a digest);
- no `pull_request_target` triggers;
- no `permissions: write-all`;
- every job declares a `permissions:` block (or the workflow does, for reusable callers);
- no `${{ github.event.* }}` interpolation directly inside `run:` scripts (script injection).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

SHA_RE = re.compile(r"@[0-9a-f]{40}(\s|$)")
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}")
INJECTION_RE = re.compile(r"\$\{\{\s*github\.event\.(pull_request|issue|comment|review|head_commit|commits)\b[^}]*\}\}")
LOCAL_PREFIXES = ("./",)
# First-party reusable workflows from the central repository may be referenced by branch/tag in templates.
FIRST_PARTY_PREFIX = "arijitaich-og1o/ai-sdlc-gate/.github/workflows/"


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return [f"{path}: YAML error: {exc}"]

    on = data.get("on") or data.get(True) or {}
    if isinstance(on, dict) and "pull_request_target" in on or isinstance(on, list) and "pull_request_target" in on:
        errors.append(f"{path}: `pull_request_target` is not allowed")
    if data.get("permissions") == "write-all":
        errors.append(f"{path}: workflow-level `permissions: write-all`")

    for m in re.finditer(r"^\s*-?\s*uses:\s*([^\s#]+)", text, flags=re.M):
        ref = m.group(1).strip().strip("\"'")
        if ref.startswith(LOCAL_PREFIXES) or ref.startswith(FIRST_PARTY_PREFIX):
            continue
        if ref.startswith("docker://"):
            if not DIGEST_RE.search(ref):
                errors.append(f"{path}: docker action not pinned to a digest: {ref}")
            continue
        if not SHA_RE.search(ref + " "):
            errors.append(f"{path}: action not pinned to a commit SHA: {ref}")

    jobs = data.get("jobs") or {}
    for name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if job.get("permissions") == "write-all":
            errors.append(f"{path}: job `{name}` uses `permissions: write-all`")
        if "permissions" not in job and "permissions" not in data:
            errors.append(f"{path}: job `{name}` has no `permissions:` block")
        for step in job.get("steps") or []:
            run = step.get("run") if isinstance(step, dict) else None
            if run and INJECTION_RE.search(str(run)):
                errors.append(f"{path}: job `{name}` step `{step.get('name', '?')}` interpolates github.event.* inside `run:` (use an env var)")
    return errors


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or [Path(".github/workflows")]
    files: list[Path] = []
    for r in roots:
        if r.is_file():
            files.append(r)
        elif r.is_dir():
            files.extend(sorted(p for p in r.rglob("*.y*ml") if "workflow" in p.name or p.parent.name == "workflows"))
    if not files:
        print("no workflow files found", file=sys.stderr)
        return 1
    errors: list[str] = []
    for f in files:
        errors.extend(check_file(f))
    if errors:
        print("Workflow hygiene FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {len(files)} workflow file(s) pass hygiene checks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
