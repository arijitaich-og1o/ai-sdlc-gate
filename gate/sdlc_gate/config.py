"""Configuration loading and shared constants."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SEVERITIES = ["info", "low", "medium", "high", "blocker"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}

DEFAULT_PHASES = {
    1: {"slug": "01-planning", "name": "Planning"},
    2: {"slug": "02-requirements", "name": "Requirements Analysis"},
    3: {"slug": "03-design", "name": "Design"},
    4: {"slug": "04-development", "name": "Development"},
    5: {"slug": "05-testing", "name": "Testing"},
    6: {"slug": "06-deployment", "name": "Deployment"},
    7: {"slug": "07-maintenance", "name": "Maintenance"},
}

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "llm": {
        "base_url_env": "LITELLM_BASE_URL",
        "api_key_env": "LITELLM_API_KEY",
        # Model names are delivered by the key broker / LITELLM_MODELS and never stored in the repository.
        "review_model": "",
        "judge_model": "",
        "fallback_models": [],
        "timeout_seconds": 180,
        "max_retries": 3,
        "temperature": 0,
        "max_output_tokens": 8000,
    },
    "phases": DEFAULT_PHASES,
    "intents": {
        "plan": [1, 2],
        "design": [2, 3],
        "commit": [3, 4, 5],
        "push": [3, 4, 5],
        "pr": [3, 4, 5],
        "release": [3, 4, 5, 6, 7],
        "deploy": [3, 4, 5, 6, 7],
        "hotfix": [4, 5, 6, 7],
        "maintenance": [4, 5, 7],
    },
    "intent_detection": {
        "trailer": "SDLC-Intent",
        "branch_patterns": [],
        "path_patterns": [],
        "default": "commit",
    },
    "gate": {
        "fail_on": "high",
        "fail_closed": True,
        "max_diff_bytes": 400_000,
        "max_file_bytes": 120_000,
        "exclude_globs": [],
    },
    "prechecks": {
        "enabled": True,
        "max_file_size_bytes": 5_000_000,
        "secret_allow_regexes": [],
    },
    "skip": {
        "enabled": True,
        "min_reason_chars": 40,
        "trailer_phases": "SDLC-Skip",
        "trailer_reason": "SDLC-Skip-Reason",
        "non_skippable_categories": [
            "secret-exposure",
            "hardcoded-credential",
            "known-vulnerable-dependency",
        ],
        "never_skippable_phases": [],
        "require_approval_for_phases": [],
        "approval_label": "sdlc-skip-approved",
    },
    "metrics": {
        "central_repo": "arijitaich-og1o/ai-sdlc-gate",
        "dispatch_event": "sdlc-gate-result",
        "branch": "metrics",
    },
    "identity": {
        "provider": "entra",
        "authority": "https://login.microsoftonline.com",
        "tenant": "",
        "client_id": "",
        "allowed_domains": [],
        "required": False,
    },
    "challenge": {
        "min_improvement": 0.02,
        "verify_merge": True,
        "weights": {"recall": 0.6, "precision": 0.25, "clarity": 0.15},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    data: dict[str, Any] = field(default_factory=lambda: _deep_merge(DEFAULT_CONFIG, {}))
    source: Path | None = None

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Config":
        candidates: list[Path] = []
        if path:
            candidates.append(Path(path))
        env_path = os.environ.get("SDLC_GATE_CONFIG")
        if env_path:
            candidates.append(Path(env_path))
        candidates.append(Path.cwd() / "gate.config.yaml")
        for c in candidates:
            if c.is_file():
                with c.open("r", encoding="utf-8") as fh:
                    raw = yaml.safe_load(fh) or {}
                if not isinstance(raw, dict):
                    raise ValueError(f"Config at {c} must be a mapping")
                merged = _deep_merge(DEFAULT_CONFIG, raw)
                merged["phases"] = {int(k): v for k, v in merged["phases"].items()}
                return cls(data=merged, source=c)
        cfg = cls()
        cfg.data["phases"] = {int(k): v for k, v in cfg.data["phases"].items()}
        return cfg

    # --- convenience accessors -------------------------------------------------
    @property
    def llm(self) -> dict[str, Any]:
        return self.data["llm"]

    @property
    def phases(self) -> dict[int, dict[str, str]]:
        return self.data["phases"]

    @property
    def intents(self) -> dict[str, list[int]]:
        return {k: [int(p) for p in v] for k, v in self.data["intents"].items()}

    @property
    def gate(self) -> dict[str, Any]:
        return self.data["gate"]

    @property
    def skip(self) -> dict[str, Any]:
        return self.data["skip"]

    @property
    def metrics(self) -> dict[str, Any]:
        return self.data["metrics"]

    @property
    def challenge(self) -> dict[str, Any]:
        return self.data["challenge"]

    @property
    def prechecks(self) -> dict[str, Any]:
        return self.data["prechecks"]

    @property
    def intent_detection(self) -> dict[str, Any]:
        return self.data["intent_detection"]

    @property
    def identity(self) -> dict[str, Any]:
        return self.data.get("identity", {})


    def phase_slug(self, phase: int) -> str:
        return self.phases[int(phase)]["slug"]

    def phase_name(self, phase: int) -> str:
        return self.phases[int(phase)]["name"]

    def fail_threshold(self, override: str | None = None) -> int:
        sev = (override or self.gate.get("fail_on") or "high").lower()
        if sev not in SEVERITY_RANK:
            raise ValueError(f"Unknown severity threshold: {sev}")
        return SEVERITY_RANK[sev]


def severity_rank(sev: str) -> int:
    return SEVERITY_RANK.get((sev or "").lower(), 0)


def normalize_severity(sev: str | None) -> str:
    s = (sev or "").strip().lower()
    aliases = {
        "critical": "blocker",
        "block": "blocker",
        "blocking": "blocker",
        "error": "high",
        "major": "high",
        "warning": "medium",
        "warn": "medium",
        "moderate": "medium",
        "minor": "low",
        "note": "info",
        "informational": "info",
        "suggestion": "info",
    }
    s = aliases.get(s, s)
    return s if s in SEVERITY_RANK else "medium"
