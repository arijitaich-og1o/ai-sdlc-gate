from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from sdlc_gate import orggate

NOW = datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fake_github(state: dict):
    """Minimal GitHub API double: one org with two repos, one open PR, pushes on main."""
    statuses = state.setdefault("statuses", {})  # sha -> [status dicts]
    posted = state.setdefault("posted", [])

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        q = dict(request.url.params)
        if p == "/orgs/og1o/repos":
            if q.get("page", "1") != "1":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[
                {"full_name": "og1o/shop", "default_branch": "main", "archived": False},
                {"full_name": "og1o/old", "default_branch": "main", "archived": True},
                {"full_name": "og1o/ai-sdlc-gate", "default_branch": "main", "archived": False},
            ])
        if p == "/repos/og1o/shop/pulls":
            if q.get("page", "1") != "1":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[
                {"number": 7, "draft": False, "head": {"sha": "pr7head", "ref": "feature/x"}, "base": {"sha": "mainbase"}, "user": {"login": "priya-dev"}},
                {"number": 8, "draft": True, "head": {"sha": "draft", "ref": "wip"}, "base": {"sha": "mainbase"}, "user": {"login": "x"}},
            ])
        if p == "/repos/og1o/shop/commits" and "sha" in q:
            if q["sha"] == "main":
                return httpx.Response(200, json=[
                    {"sha": "m3", "parents": [{"sha": "m2"}], "author": {"login": "arijit"}},
                    {"sha": "m2", "parents": [{"sha": "m1"}], "author": {"login": "arijit"}},
                    {"sha": "m1", "parents": [{"sha": "m0"}], "author": {"login": "someone"}},
                ])
            return httpx.Response(404, json={"message": "Branch not found"})
        m = p.rsplit("/", 1)
        if p.endswith("/status"):
            sha = p.split("/commits/")[1].split("/")[0]
            return httpx.Response(200, json={"statuses": statuses.get(sha, [])})
        if p.endswith("/check-runs"):
            return httpx.Response(200, json={"total_count": 0, "check_runs": []})
        if "/statuses/" in p and request.method == "POST":
            sha = m[1]
            body = json.loads(request.content)
            posted.append((sha, body))
            statuses.setdefault(sha, []).append({"context": body["context"], "state": body["state"], "updated_at": _iso(NOW)})
            return httpx.Response(201, json=body)
        return httpx.Response(404, json={"message": f"no route {p}"})

    return orggate.GitHub("token", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_discover_finds_pr_heads_and_pushes_and_skips_gated():
    state = {"statuses": {"m2": [{"context": "SDLC Gate", "state": "success", "updated_at": _iso(NOW - timedelta(hours=1))}]}}
    gh = _fake_github(state)
    cands = orggate.discover(gh, ["og1o"], exclude_repos=["og1o/ai-sdlc-gate"], extra_branches=())
    by_sha = {c.sha: c for c in cands}
    assert set(by_sha) == {"pr7head", "m3"}
    pr = by_sha["pr7head"]
    assert pr.event == "pull_request" and pr.pr_number == 7 and pr.base == "mainbase" and pr.actor == "priya-dev" and pr.ref == "feature/x"
    push = by_sha["m3"]
    assert push.event == "push" and push.base == "m2" and push.actor == "arijit" and push.ref == "main"
    assert all(c.repo == "og1o/shop" for c in cands)  # archived + excluded repos skipped, drafts skipped


def test_discover_respects_existing_and_fresh_pending_results():
    fresh = _iso(NOW - timedelta(minutes=2))
    stale = _iso(NOW - timedelta(hours=3))
    state = {"statuses": {
        "pr7head": [{"context": "SDLC Gate", "state": "pending", "updated_at": fresh}],
        "m3": [{"context": "SDLC Gate", "state": "pending", "updated_at": stale}],
    }}
    cands = orggate.discover(_fake_github(state), ["og1o"], exclude_repos=["og1o/ai-sdlc-gate"], extra_branches=())
    assert [c.sha for c in cands] == ["m3"]  # fresh pending skipped, stale pending re-gated

    state = {"statuses": {"pr7head": [{"context": "SDLC Gate", "state": "failure", "updated_at": fresh}], "m3": [{"context": "SDLC Gate", "state": "success", "updated_at": fresh}]}}
    assert orggate.discover(_fake_github(state), ["og1o"], exclude_repos=["og1o/ai-sdlc-gate"], extra_branches=()) == []


def test_push_base_falls_back_to_parent_when_nothing_gated():
    cands = orggate.discover(_fake_github({}), ["og1o"], exclude_repos=["og1o/ai-sdlc-gate"], extra_branches=())
    push = next(c for c in cands if c.event == "push")
    assert push.base == "m2"  # parent of m3


def test_set_status_posts_and_validates():
    state: dict = {}
    gh = _fake_github(state)
    orggate.set_status(gh, "og1o/shop", "m3", "failure", "x" * 200, "https://example/run")
    sha, body = state["posted"][0]
    assert sha == "m3" and body["state"] == "failure" and body["context"] == "SDLC Gate" and len(body["description"]) == 140
    with pytest.raises(orggate.GitHubError):
        orggate.set_status(gh, "bad slug", "m3", "success", "d")
    with pytest.raises(orggate.GitHubError):
        orggate.set_status(gh, "og1o/shop", "m3", "maybe", "d")


def test_github_requires_token():
    with pytest.raises(orggate.GitHubError):
        orggate.GitHub("")
