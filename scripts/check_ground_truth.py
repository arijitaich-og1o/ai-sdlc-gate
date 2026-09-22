#!/usr/bin/env python3
"""Validate trials/*/GROUND_TRUTH.yaml files: structure, referenced files exist, ids unique."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

SEVERITIES = {"info", "low", "medium", "high", "blocker"}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("trials")
    errors: list[str] = []
    seen_phases: set[int] = set()
    for gt in sorted(root.glob("*/GROUND_TRUTH.yaml")):
        data = yaml.safe_load(gt.read_text(encoding="utf-8")) or {}
        phase = data.get("phase")
        if not isinstance(phase, int) or not 1 <= phase <= 8:
            errors.append(f"{gt}: `phase` must be an int 1-8")
        elif phase in seen_phases:
            errors.append(f"{gt}: duplicate phase {phase}")
        else:
            seen_phases.add(phase)
        if not gt.parent.name.startswith(f"{phase:02d}-") if isinstance(phase, int) else True:
            errors.append(f"{gt}: directory name does not match phase {phase}")
        defects = data.get("defects") or []
        if len(defects) < 5:
            errors.append(f"{gt}: at least 5 planted defects are required (found {len(defects)})")
        ids: set[str] = set()
        for d in defects:
            did = str(d.get("id", ""))
            if not did or did in ids:
                errors.append(f"{gt}: missing or duplicate defect id {did!r}")
            ids.add(did)
            if d.get("severity") not in SEVERITIES:
                errors.append(f"{gt}: defect {did}: invalid severity {d.get('severity')!r}")
            kws = d.get("keywords") or []
            if not isinstance(kws, list) or len(kws) < 1:
                errors.append(f"{gt}: defect {did}: keywords must be a non-empty list")
            f = d.get("file")
            if f and not (root / f).is_file():
                errors.append(f"{gt}: defect {did}: referenced file not found: {f}")
        other_files = [p for p in gt.parent.rglob("*") if p.is_file() and p.name not in {"GROUND_TRUTH.yaml", "README.md"}]
        if not other_files:
            errors.append(f"{gt}: phase directory has no content to review")
    if seen_phases != set(range(1, 9)):
        errors.append(f"expected ground truth for phases 1-8, found {sorted(seen_phases)}")
    if errors:
        print("Ground truth validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: ground truth present and valid for {len(seen_phases)} phases")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
