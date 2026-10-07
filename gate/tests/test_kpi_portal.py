"""Portal export: aggregate-only, small teams folded and recomputed, stable pseudonymous labels, versioned."""
from __future__ import annotations

import json
from pathlib import Path

from ai_sdlc_gate import kpi, kpi_sources
from ai_sdlc_gate.cli import main
from ai_sdlc_gate.metrics import ingest_event
from tests.test_kpi import ev

SALT = kpi_sources.person_salt.__name__  # any fixed string works; derived so no literal key sits in the tests
SKIP = {"requested": True, "valid": True, "requested_phases": [4], "valid_phases": [4],
        "reason": "Spike SPK-1 for the cart rewrite", "errors": []}


def _team_runs(repo: str, people: int, start: int, verdicts=("pass", "fail")) -> list[dict]:
    out = []
    for i in range(people):
        for j, verdict in enumerate(verdicts):
            n = start + i * 10 + j
            out.append(ev(n, f"2026-10-0{1 + (n % 6)}T1{j}:{i:02d}:00+00:00", verdict, repo=repo,
                          developer_email=f"{repo.split('/')[0]}.dev{i}@example.invalid"))
    return out


def test_small_teams_are_folded_and_a_small_other_group_is_not_shown():
    events = _team_runs("big/app", 5, 0) + _team_runs("tiny/x", 1, 500) + [ev(900, "2026-10-03T09:00:00+00:00", repo="unknown/unknown")]
    p = kpi.portal_export(events, salt=SALT)
    big = kpi.team_label("big", SALT)
    assert list(p["teams"]) == [big]  # "tiny" (1 user) and the unattributed runs fold; the fold has < 5 users
    assert list(p["adoption"]) == [big] and all(set(c) <= {big} for c in p["cases_by_month"].values())
    assert set(p["users"]["by_team"]) == {big} and p["users"]["by_team"][big]["gate_users"] == 5
    assert p["overall"]["runs"] == len(events)  # the organisation-wide numbers still count every run
    assert p["suppression"] == {"min_group": 5, "teams_shown": 1, "teams_folded": 2, "other_teams_shown": False,
                                "labels": "pseudonymous", "organisation_below_min_group": False}


def test_other_teams_is_recomputed_from_rows_when_large_enough():
    small_a = _team_runs("a/x", 3, 0, verdicts=("pass", "pass", "pass"))
    small_b = _team_runs("b/y", 3, 500, verdicts=("fail",))
    p = kpi.portal_export(small_a + small_b, salt=SALT)
    other = p["teams"][kpi.OTHER_TEAMS]
    assert other["runs"] == 12 and other["gate_pass_rate"] == 0.75  # 9 of 12 runs, not the mean of 1.0 and 0.0
    assert p["users"]["by_team"][kpi.OTHER_TEAMS]["gate_users"] == 6
    assert p["suppression"]["other_teams_shown"] is True and p["suppression"]["teams_shown"] == 0


def test_labels_are_stable_pseudonyms_unless_real_names_are_approved():
    base = _team_runs("big/app", 5, 0)
    first = kpi.portal_export(base, salt=SALT)
    more = kpi.portal_export(base + _team_runs("alpha/svc", 5, 500), salt=SALT)
    label = kpi.team_label("big", SALT)
    assert label.startswith("Team ") and "big" not in label
    assert label in first["teams"] and label in more["teams"]  # unchanged when another team appears
    assert kpi.team_label("big", "another-machine") != label  # keyed: not reversible by guessing team names
    real = kpi.portal_export(base, salt=SALT, real_team_names=True)
    assert list(real["teams"]) == ["big"] and real["suppression"]["labels"] == "real"


def test_portal_file_carries_no_repository_person_or_free_text():
    events = _team_runs("big/app", 5, 0)
    events[0] = {**events[0], "skip": SKIP, "findings_brief": [
        {"phase": 4, "severity": "high", "category": "xss", "title": "Unescaped name in view.py", "file": "app/view.py", "waived": False}]}
    git_rows = [{"repo": "big/app", "ts": "2026-10-02T10:00:00+00:00", "author": kpi_sources.person_key("big.dev0@example.invalid", SALT),
                 "merge": False, "revert": False, "fix": True}]
    p = kpi.portal_export(events, salt=SALT, git_rows=git_rows)
    blob = json.dumps(p)
    for leak in ("big/app", "example.invalid", "SPK-1", "Unescaped", "view.py", kpi_sources.person_key("big.dev0@example.invalid", SALT)):
        assert leak not in blob, leak
    assert not {"repos", "skip_reasons"} & set(p)
    assert "top_categories" not in json.dumps({k: p[k] for k in ("overall", "teams", "weeks")})
    assert p["quality_outcome"]["scope"] == "pilot" and p["quality_outcome"]["repositories"] == 1


def test_schema_version_and_determinism():
    events = _team_runs("big/app", 5, 0)
    a, b = kpi.portal_export(events, salt=SALT), kpi.portal_export(list(reversed(events)), salt=SALT)
    assert a == b
    assert a["schema"] == kpi.PORTAL_SCHEMA and a["dataset_version"] == kpi.DATASET_VERSION == 2
    assert json.loads(kpi.export(events, salt=SALT)["kpi-runs.json"])["dataset_version"] == 2


def test_cli_portal_writes_only_the_sanitised_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path / "home"))
    events_dir = tmp_path / "events"
    for e in _team_runs("big/app", 5, 0):
        ingest_event(e, events_dir)
    out = tmp_path / "portal"
    assert main(["kpi", "export", "--events-dir", str(events_dir), "--out", str(out), "--portal"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["kpi-portal.json"]
    data = json.loads((out / "kpi-portal.json").read_text(encoding="utf-8"))
    assert data["schema"] == kpi.PORTAL_SCHEMA and len(data["teams"]) == 1
    assert main(["kpi", "export", "--events-dir", str(events_dir), "--out", str(tmp_path / "x"), "--real-team-names"]) != 0


def test_outcomes_from_few_committers_are_a_pilot_even_across_many_repos():
    events = _team_runs("big/app", 5, 0)
    one_person = kpi_sources.person_key("maintainer@example.invalid", SALT)
    git_rows = [{"repo": f"own/r{i}", "ts": "2026-10-02T10:00:00+00:00", "author": one_person,
                 "merge": False, "revert": False, "fix": False} for i in range(6)]
    p = kpi.portal_export(events, salt=SALT, git_rows=git_rows)
    assert p["quality_outcome"]["repositories"] == 6 and p["quality_outcome"]["scope"] == "pilot"
