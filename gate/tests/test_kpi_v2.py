"""KPI v2: measured streams only (git history, pull requests, teams, adoption) and attributable runs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_sdlc_gate import gitutil, kpi, kpi_sources
from ai_sdlc_gate.cli import main
from ai_sdlc_gate.metrics import ingest_event
from tests.conftest import git
from tests.test_kpi import ev

SALT = "0123456789abcdef0123456789abcdef"


# ----------------------------------------------------------------------------- attributable runs

@pytest.mark.parametrize("url,slug", [
    ("https://github.com/otto-ec/kraken_samplenator.git", "otto-ec/kraken_samplenator"),
    ("git@github.com:OG-DW/sofa_docs.git", "OG-DW/sofa_docs"),
    ("https://gitlab.com/group/proj", "group/proj"),
    ("git@bitbucket.org:team/repo.git", "team/repo"),
    ("https://dev.azure.com/ottogroup/Commerce/_git/checkout-api", "ottogroup/checkout-api"),
    ("https://ottogroup@dev.azure.com/ottogroup/Commerce/_git/checkout-api", "ottogroup/checkout-api"),
    ("git@ssh.dev.azure.com:v3/ottogroup/Commerce/checkout-api", "ottogroup/checkout-api"),
    ("https://ottogroup.visualstudio.com/Commerce/_git/checkout-api", "ottogroup/checkout-api"),
])
def test_repo_slug_from_common_remotes(tmp_repo: Path, url, slug):
    git("remote", "add", "origin", url, cwd=tmp_repo)
    assert gitutil.repo_slug(tmp_repo) == slug


def test_repo_without_remote_is_still_attributable(tmp_repo: Path):
    assert gitutil.repo_slug(tmp_repo) == "local/repo"


def test_branch_is_named_before_the_first_commit(tmp_path: Path):
    repo = tmp_path / "fresh"
    repo.mkdir()
    git("init", "-q", "-b", "feature/start", cwd=repo)
    assert gitutil.current_branch(repo) == "feature/start"  # rev-parse --abbrev-ref said HEAD here


# ----------------------------------------------------------------------------- git history

def test_collect_git_keeps_metadata_only(tmp_repo: Path):
    for msg in ("feat: add cart", "fix(cart): rounding", 'Revert "feat: add cart"\n\nThis reverts commit 1234567.'):
        (tmp_repo / "f.txt").write_text(msg, encoding="utf-8")
        git("add", ".", cwd=tmp_repo)
        git("commit", "-q", "-m", msg, cwd=tmp_repo)
    rows = kpi_sources.collect_git(tmp_repo, SALT, slug="org/app")
    # Commits made within one second sort by sha, so check the classification by count, not position.
    flags = sorted((r["fix"], r["revert"]) for r in rows)
    assert flags.count((True, False)) == 1 and flags.count((False, True)) == 1 and flags.count((False, False)) == len(rows) - 2
    assert all(r["repo"] == "org/app" and len(r["author"]) == 16 for r in rows)
    blob = json.dumps(rows)
    assert "dev@example.com" not in blob and "rounding" not in blob and "add cart" not in blob


# ----------------------------------------------------------------------------- pull requests

def test_collect_prs_reads_cycle_and_review_effort():
    pulls = [
        {"number": 2, "created_at": "2026-10-01T10:00:00Z", "merged_at": "2026-10-01T16:00:00Z", "title": "feat: x"},
        {"number": 3, "created_at": "2026-10-02T10:00:00Z", "merged_at": None, "title": "wip"},
        {"number": 4, "created_at": "2026-10-03T10:00:00Z", "merged_at": "2026-10-03T11:00:00Z", "title": 'Revert "feat: x"'},
    ]
    reviews = {2: [{"state": "CHANGES_REQUESTED"}, {"state": "APPROVED"}, {"state": "PENDING"}], 4: [{"state": "APPROVED"}]}
    calls = []

    def fetch(path: str):
        calls.append(path)
        if "/pulls?" in path:
            return pulls if path.endswith("page=1") else []
        n = int(path.split("/pulls/")[1].split("/")[0].split("?")[0])
        return reviews[n] if "/reviews" in path else {"review_comments": 5 if n == 2 else 0}

    rows = kpi_sources.collect_prs("org/app", fetch)
    by = {r["number"]: r for r in rows}
    assert by[2]["reviews"] == 2 and by[2]["changes_requested"] == 1 and by[2]["review_comments"] == 5
    assert by[3]["reviews"] is None  # not merged: no detail calls
    assert by[4]["revert"] is True
    assert not any("/pulls/3" in c for c in calls)
    with pytest.raises(ValueError):
        kpi_sources.collect_prs("not a slug", fetch)


# ----------------------------------------------------------------------------- teams, adoption, users

def test_team_map_then_owner_then_unattributed():
    teams = {"Checkout": ["otto-ec/kraken_*"], "Docs": ["og-dw/sofa_docs"]}
    assert kpi.team_of("otto-ec/kraken_samplenator", teams) == "Checkout"
    assert kpi.team_of("OG-DW/sofa_docs", teams) == "Docs"  # case-insensitive
    assert kpi.team_of("OG-DW/sofa_poc", teams) == "OG-DW"
    assert kpi.team_of("unknown/unknown", teams) == kpi.UNATTRIBUTED_TEAM


def _runs(team_repo: str, per_week: list[int], start_monday: str = "2026-09-07") -> list[dict]:
    from datetime import date, timedelta

    out, n = [], 0
    d0 = date.fromisoformat(start_monday)
    for w, count in enumerate(per_week):
        for i in range(count):
            n += 1
            day = d0 + timedelta(weeks=w, days=i % 5)
            out.append(ev(hash((team_repo, n)) % 10**6, f"{day.isoformat()}T10:{i % 60:02d}:00+00:00", repo=team_repo))
    return out


def test_adoption_phases_follow_the_documented_streak_rule():
    events = _runs("org/app", [6, 6, 0, 6, 6, 6, 6])
    a = kpi.adoption(kpi.build_rows(events))["org"]
    assert [w["phase"] for w in a["weeks"]] == ["experimental", "regular", "experimental", "experimental", "regular", "regular", "operational"]
    assert [w["runs"] for w in a["weeks"]] == [6, 6, 0, 6, 6, 6, 6]
    assert a["weeks"][2]["week"] == "2026-W39"  # the empty week keeps its own ISO label
    assert a["phase"] == "operational"


def test_cases_by_month_stack_by_team():
    events = [ev(1, "2026-09-30T10:00:00+00:00", repo="a/x"), ev(2, "2026-10-01T10:00:00+00:00", repo="a/x"),
              ev(3, "2026-10-02T10:00:00+00:00", repo="b/y")]
    assert kpi.cases_by_month(kpi.build_rows(events)) == {"2026-09": {"a": 1}, "2026-10": {"a": 1, "b": 1}}


def test_people_counts_are_suppressed_below_five():
    def run(n, email, repo="org/app"):
        return ev(n, f"2026-10-0{1 + n % 5}T10:00:00+00:00", repo=repo, developer_email=email)

    four = [run(i, f"dev{i}@example.invalid") for i in range(4)]
    five = four + [run(9, "dev9@example.invalid")]
    git_rows = [{"repo": "org/app", "author": kpi_sources.person_key(f"dev{i}@example.invalid", SALT), "merge": False} for i in range(5)]
    git_rows += [{"repo": "org/app", "author": kpi_sources.person_key("other@example.invalid", SALT), "merge": False}]
    u4 = kpi.users(kpi.gate_users(four, None, SALT), git_rows, None, {"org/app"})
    assert u4["total_gate_users"] is None and u4["by_team"]["org"]["gate_users"] is None and u4["by_team"]["org"]["coverage"] is None
    u5 = kpi.users(kpi.gate_users(five, None, SALT), git_rows, None, {"org/app"})
    assert u5["by_team"]["org"] == {"gate_users": 5, "committers": 6, "coverage": round(4 / 6, 4)}  # dev9 has no commits
    summary = kpi.export(five, salt=SALT)["kpi-summary.json"]
    assert "example.invalid" not in summary and kpi_sources.person_key("dev1@example.invalid", SALT) not in summary


# ----------------------------------------------------------------------------- outcomes

def test_quality_outcome_splits_by_adoption_date():
    rows = kpi.build_rows([ev(1, "2026-10-01T00:00:00+00:00", repo="org/app")])
    adopted = kpi._adoption_dates(rows)
    git_rows = [
        {"repo": "org/app", "ts": "2026-09-20T10:00:00+00:00", "merge": False, "revert": True, "fix": False},
        {"repo": "org/app", "ts": "2026-09-21T10:00:00+00:00", "merge": False, "revert": False, "fix": True},
        {"repo": "org/app", "ts": "2026-10-02T10:00:00+00:00", "merge": False, "revert": False, "fix": False},
        {"repo": "org/app", "ts": "2026-10-03T10:00:00+00:00", "merge": True, "revert": False, "fix": False},  # merges skipped
        {"repo": "org/other", "ts": "2026-10-02T10:00:00+00:00", "merge": False, "revert": False, "fix": True},
    ]
    q = kpi.quality_outcome(git_rows, adopted)
    assert q["gated_before"] == {"commits": 2, "repos": 1, "revert_rate": 0.5, "fix_commit_rate": 0.5}
    assert q["gated_after"] == {"commits": 1, "repos": 1, "revert_rate": 0.0, "fix_commit_rate": 0.0}
    assert q["ungated"]["fix_commit_rate"] == 1.0
    assert kpi.quality_outcome([], adopted) is None


def test_review_effect_compares_merged_prs():
    adopted = {"org/app": "2026-10-01T00:00:00+00:00"}
    prs = [
        {"repo": "org/app", "created_at": "2026-09-20T00:00:00Z", "merged_at": "2026-09-21T00:00:00Z", "reviews": 3, "changes_requested": 1, "review_comments": 8, "revert": False},
        {"repo": "org/app", "created_at": "2026-10-02T00:00:00Z", "merged_at": "2026-10-02T06:00:00Z", "reviews": 1, "changes_requested": 0, "review_comments": 2, "revert": False},
        {"repo": "org/app", "created_at": "2026-10-03T00:00:00Z", "merged_at": None, "reviews": None, "changes_requested": None, "review_comments": None, "revert": False},
    ]
    r = kpi.review_effect(prs, adopted)
    assert r["gated_before"]["cycle_hours_median"] == 24.0 and r["gated_before"]["reviews_median"] == 3.0
    assert r["gated_after"] == {"prs": 1, "repos": 1, "cycle_hours_median": 6.0, "reviews_median": 1.0, "changes_requested_share": 0.0,
                                "review_comments_median": 2.0, "revert_pr_rate": 0.0}
    assert kpi.review_effect([prs[2]], adopted) is None


# ----------------------------------------------------------------------------- end to end

def test_cli_export_with_all_streams(tmp_path: Path, tmp_repo: Path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path / "home"))  # the per-machine salt lives here
    events_dir = tmp_path / "events"
    for i, verdict in enumerate(["fail", "pass", "pass"]):
        ingest_event(ev(i, f"2026-10-0{i + 1}T10:00:00+00:00", verdict, repo="org/app"), events_dir)
    git("remote", "add", "origin", "https://github.com/org/app.git", cwd=tmp_repo)
    git_file, pr_file, teams_file, out = tmp_path / "git.jsonl", tmp_path / "prs.jsonl", tmp_path / "teams.yaml", tmp_path / "kpi"
    assert main(["kpi", "collect-git", "--repo-dir", str(tmp_repo), "--out", str(git_file)]) == 0
    kpi_sources.write_jsonl([{"repo": "org/app", "number": 1, "created_at": "2026-10-02T00:00:00Z", "merged_at": "2026-10-02T05:00:00Z",
                              "reviews": 1, "changes_requested": 0, "review_comments": 0, "revert": False}], pr_file)
    teams_file.write_text("teams:\n  Checkout: ['org/*']\n", encoding="utf-8")
    assert main(["kpi", "export", "--events-dir", str(events_dir), "--out", str(out), "--git", str(git_file),
                 "--prs", str(pr_file), "--teams", str(teams_file)]) == 0
    s = json.loads((out / "kpi-summary.json").read_text(encoding="utf-8"))
    assert list(s["teams"]) == ["Checkout"] and s["sources"]["team_map"] is True
    assert s["sources"]["git_commits"] == 1 and s["quality_outcome"]["gated_after"]["commits"] == 1  # committed now, after the first run
    assert s["review_effect"]["gated_after"]["cycle_hours_median"] == 5.0
    assert "Checkout" in (out / "kpi-runs.csv").read_text(encoding="utf-8").splitlines()[1]


# ----------------------------------------------------------------------------- hardening (self-gate review)

def test_person_keys_are_keyed_and_need_a_salt(tmp_path: Path):
    a = kpi_sources.person_key("dev@example.invalid", SALT)
    assert a == kpi_sources.person_key(" DEV@example.invalid ", SALT)  # normalised
    assert a != kpi_sources.person_key("dev@example.invalid", "another-salt")  # not reversible by hashing a guess list
    with pytest.raises(ValueError):
        kpi_sources.person_key("dev@example.invalid", "")
    salt = kpi_sources.person_salt(tmp_path)
    assert salt == kpi_sources.person_salt(tmp_path) and len(salt) == 32  # created once, then reused


def test_team_map_problems_are_reported():
    teams = {"A": ["org/*"], "B": ["org/app"], "C": ["nothing-matches"], "D": ["ghost/*"]}
    problems = kpi.validate_teams(teams, ["org/app", "org/web"])
    assert any("org/app" in p and "'A'" in p for p in problems)  # overlap, first team in name order wins
    assert any("'C'" in p and "no owner/ part" in p for p in problems)
    assert any("'D'" in p and "matches no repository" in p for p in problems)


def test_pr_collector_rejects_owners_github_cannot_have():
    with pytest.raises(ValueError):
        kpi_sources.collect_prs("owner.with.dots/repo", lambda path: [])


# ----------------------------------------------------------------------------- gh output decoding (Windows)

def test_gh_fetch_decodes_utf8_whatever_the_locale(monkeypatch):
    """gh writes UTF-8; on Windows the locale is cp1252, where a non-ASCII PR body made the read return None."""
    import subprocess
    import sys

    body = json.dumps([{"number": 1, "title": "Fix für Größen – ✓ 日本"}], ensure_ascii=False)
    real_run = subprocess.run
    calls = []

    def fake_run(cmd, **kw):
        calls.append(kw)
        # A real child process writing UTF-8 bytes, decoded with whatever arguments gh_fetch passes.
        script = "import sys; sys.stdout.buffer.write(" + repr(body.encode("utf-8")) + ")"
        return real_run([sys.executable, "-c", script], **kw)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert kpi_sources.gh_fetch()("/repos/org/app/pulls") == json.loads(body)
    assert calls[0]["encoding"] == "utf-8"


def test_a_failed_page_read_is_an_error_not_zero_prs():
    for bad in (None, {"message": "Bad credentials"}, "oops"):
        with pytest.raises(RuntimeError, match="unexpected response"):
            kpi_sources.collect_prs("org/app", lambda path, bad=bad: bad)
    assert kpi_sources.collect_prs("org/app", lambda path: []) == []  # an empty list is a real "no PRs"


def test_gh_fetch_reports_empty_output(monkeypatch):
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""))
    with pytest.raises(RuntimeError, match="no output"):
        kpi_sources.gh_fetch()("/repos/org/app/pulls")
