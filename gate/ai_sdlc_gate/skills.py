"""Loading and validating the eight phase skills.

A skill is a directory `skills/<NN-slug>/` containing `SKILL.md` with YAML front matter:

    ---
    name: Development Gate
    phase: 4
    version: 1.0.0
    description: ...
    ---
    <review instructions the model follows>

The repository must contain exactly one skill per SDLC phase (8 in total).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config

REQUIRED_KEYS = ("name", "phase", "version", "description")
MIN_BODY_CHARS = 400
MAX_BODY_CHARS = 60_000
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# Phrases that indicate an attempt to smuggle instructions targeting the gate itself.
FORBIDDEN_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"ignore\s+(all|any|the)?\s*(previous|prior|above|following|system)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(all|any|the)?\s*(previous|prior|above|system)",
        r"(always|please)?\s*(return|report|output|emit)\s+(zero|no|an empty|empty)\s+(findings?|issues?|problems?)",
        r"never\s+(fail|block|reject|stop)\s+(the\s+)?(gate|commit|push|review|change)",
        r"(set|mark|force)\s+(the\s+)?(phase_)?verdict\s*(to|=|:)?\s*[\"']?(pass|approved?|ok)",
        r"(mark|treat|consider)\s+(this|the\s+change|it)\s+(as\s+)?(pass|approved?|safe|clean)",
        r"you\s+are\s+now\b",
        r"new\s+(system\s+)?(instructions?|prompt)",
        r"</?(phase_skill|change_set|review_context|system)\b",
    )
]


@dataclass
class Skill:
    phase: int
    slug: str
    name: str
    version: str
    description: str
    body: str
    path: Path | None = None
    frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def markdown(self) -> str:
        return render_skill(self.frontmatter, self.body)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    text = text.lstrip("﻿")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, flags=re.S)
    if not m:
        raise ValueError("SKILL.md must start with a YAML front matter block delimited by ---")
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Front matter is not valid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise ValueError("Front matter must be a mapping")
    return fm, m.group(2)


def render_skill(frontmatter: dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


def parse_skill(text: str, path: Path | None = None, slug: str | None = None) -> Skill:
    fm, body = split_frontmatter(text)
    missing = [k for k in REQUIRED_KEYS if k not in fm]
    if missing:
        raise ValueError(f"Front matter missing keys: {', '.join(missing)}")
    try:
        phase = int(fm["phase"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Front matter `phase` must be an integer 1-8") from exc
    if phase < 1 or phase > 8:
        raise ValueError("Front matter `phase` must be between 1 and 8")
    version = str(fm["version"])
    if not SEMVER.match(version):
        raise ValueError(f"Front matter `version` must be semver (x.y.z), got {version!r}")
    body_stripped = body.strip()
    if len(body_stripped) < MIN_BODY_CHARS:
        raise ValueError(f"Skill body too short ({len(body_stripped)} chars, min {MIN_BODY_CHARS})")
    if len(body_stripped) > MAX_BODY_CHARS:
        raise ValueError(f"Skill body too long ({len(body_stripped)} chars, max {MAX_BODY_CHARS})")
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(body_stripped):
            raise ValueError(f"Skill body contains a forbidden instruction pattern: /{pat.pattern}/")
    return Skill(
        phase=phase,
        slug=slug or (path.parent.name if path else f"{phase:02d}"),
        name=str(fm["name"]),
        version=version,
        description=str(fm["description"]),
        body=body_stripped,
        path=path,
        frontmatter=fm,
    )


def load_skill_file(path: Path) -> Skill:
    return parse_skill(path.read_text(encoding="utf-8"), path=path, slug=path.parent.name)


def validate_skills_dir(skills_dir: Path, cfg: Config) -> tuple[dict[int, Skill], list[str]]:
    """Return (skills_by_phase, errors). Errors is empty when the directory is valid."""
    errors: list[str] = []
    skills: dict[int, Skill] = {}
    if not skills_dir.is_dir():
        return skills, [f"skills directory not found: {skills_dir}"]
    dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    expected = {int(p): v["slug"] for p, v in cfg.phases.items()}
    expected_slugs = set(expected.values())
    found_slugs = {d.name for d in dirs}
    for extra in sorted(found_slugs - expected_slugs):
        errors.append(f"unexpected skill directory `{extra}`; only the 8 SDLC phase skills are allowed")
    for missing in sorted(expected_slugs - found_slugs):
        errors.append(f"missing skill directory `{missing}`")
    for d in dirs:
        if d.name not in expected_slugs:
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{d.name}: SKILL.md not found")
            continue
        stray = [p.name for p in d.iterdir() if p.is_file() and p.name not in {"SKILL.md", "README.md"}]
        if stray:
            errors.append(f"{d.name}: unexpected files {stray}; a skill is SKILL.md (+ optional README.md)")
        try:
            skill = load_skill_file(skill_file)
        except Exception as exc:  # noqa: BLE001 - surfaced as a validation error
            errors.append(f"{d.name}/SKILL.md: {exc}")
            continue
        wanted_phase = next(p for p, s in expected.items() if s == d.name)
        if skill.phase != wanted_phase:
            errors.append(f"{d.name}/SKILL.md: front matter phase {skill.phase} does not match directory phase {wanted_phase}")
            continue
        if skill.phase in skills:
            errors.append(f"duplicate skill for phase {skill.phase}")
            continue
        skills[skill.phase] = skill
    if not errors and len(skills) != 8:
        errors.append(f"expected exactly 8 skills, found {len(skills)}")
    return skills, errors


def load_skills(skills_dir: Path, cfg: Config) -> dict[int, Skill]:
    skills, errors = validate_skills_dir(skills_dir, cfg)
    if errors:
        raise ValueError("Invalid skills directory:\n  - " + "\n  - ".join(errors))
    return skills
