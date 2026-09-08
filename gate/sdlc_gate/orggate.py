"""Organisation-wide gate without any file in the target repositories.

The central repository polls the organisation (schedule + manual trigger), finds pull-request heads and
pushes to default/protected branches that have not been gated yet, runs the gate on each of them, and posts a
commit status with context `SDLC Gate`. The organisation ruleset requires that status before a merge, so no
repository can opt out and no developer needs to add anything to their project.

Everything here talks to the GitHub REST API with the org-scoped SDLC_GATE_TOKEN (fine-grained PAT or GitHub App
token with Contents: read, Pull requests: write, Commit statuses: write on all repositories).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

STATUS_CONTEXT = "SDLC Gate"
CHECK_RUN_NAME = "SDLC Gate / SDLC Gate"  # produced by repositories that call the reusable workflow directly
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str, api_base: str = "https://api.github.com", client: httpx.Client | None = None) -> None:
        if not token:
            raise GitHubError("SDLC_GATE_TOKEN is required for the organisation gate")
        self.api_base = api_base.rstrip("/")
        self._client = client or httpx.Client(timeout=30)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sdlc-gate/1.0",
        }

    def get(self, path: str, params: dict[str, Any] | None = None, ok404: bool = False) -> Any:
        resp = self._client.get(f"{self.api_base}{path}", params=params, headers=self._headers)
        if resp.status_code == 404 and ok404:
            return None
        if resp.status_code >= 400:
            raise GitHubError(f"GET {path}: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def paginate(self, path: str, params: dict[str, Any] | None = None, limit: int = 1000) -> list[Any]:
        out: list[Any] = []
        page = 1
        while len(out) < limit:
            data = self.get(path, {**(params or {}), "per_page": 100, "page": page})
            if not isinstance(data, list) or not data:
                break
            out.extend(data)
            if len(data) < 100:
                break
            page += 1
        return out[:limit]

    def post(self, path: str, body: dict[str, Any]) -> Any:
        resp = self._client.post(f"{self.api_base}{path}", json=body, headers=self._headers)
        if resp.status_code >= 400:
            raise GitHubError(f"POST {path}: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.content else None


@dataclass
class Candidate:
    repo: str
    sha: str
    base: str
    ref: str
    event: str  # pull_request | push
    actor: str
    pr_number: int | None = None
    default_branch: str = "main"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_repositories(gh: GitHub, owner: str) -> list[dict[str, Any]]:
    """Repositories of an organisation, or of a user account when `owner` is not an organisation."""
    try:
        repos = gh.paginate(f"/orgs/{owner}/repos", {"type": "all", "sort": "pushed", "direction": "desc"})
    except GitHubError as exc:
        if "404" not in str(exc):
            raise
        repos = gh.paginate(f"/users/{owner}/repos", {"type": "owner", "sort": "pushed", "direction": "desc"})
    return [r for r in repos if not r.get("archived") and not r.get("disabled")]


def gate_state(gh: GitHub, repo: str, sha: str, context: str = STATUS_CONTEXT) -> str | None:
    """Return success|failure|error|pending if the commit already has a gate result, else None."""
    data = gh.get(f"/repos/{repo}/commits/{sha}/status", ok404=True)
    if data:
        for st in data.get("statuses") or []:
            if st.get("context") == context:
                return str(st.get("state"))
    runs = gh.get(f"/repos/{repo}/commits/{sha}/check-runs", {"check_name": CHECK_RUN_NAME}, ok404=True)
    if runs and runs.get("total_count"):
        for run in runs.get("check_runs") or []:
            if run.get("status") != "completed":
                return "pending"
            return "success" if run.get("conclusion") == "success" else "failure"
    return None


def _stale(pending_since: str | None, max_pending_minutes: int) -> bool:
    if not pending_since:
        return True
    try:
        ts = datetime.fromisoformat(pending_since.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - ts > timedelta(minutes=max_pending_minutes)


def _pending_since(gh: GitHub, repo: str, sha: str, context: str) -> str | None:
    data = gh.get(f"/repos/{repo}/commits/{sha}/status", ok404=True) or {}
    for st in data.get("statuses") or []:
        if st.get("context") == context:
            return st.get("updated_at")
    return None


def discover(
    gh: GitHub,
    owners: Iterable[str],
    exclude_repos: Iterable[str] = (),
    since_minutes: int = 120,
    max_candidates: int = 25,
    max_pending_minutes: int = 45,
    context: str = STATUS_CONTEXT,
    extra_branches: Iterable[str] = ("develop",),
) -> list[Candidate]:
    exclude = {r.lower() for r in exclude_repos}
    since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[Candidate] = []
    for owner in owners:
        for repo in list_repositories(gh, owner):
            full = repo["full_name"]
            if full.lower() in exclude:
                continue
            default_branch = repo.get("default_branch") or "main"
            # Open pull requests: gate the head commit.
            for pr in gh.paginate(f"/repos/{full}/pulls", {"state": "open", "sort": "updated", "direction": "desc"}, limit=100):
                if pr.get("draft"):
                    continue
                head = pr["head"]["sha"]
                state = gate_state(gh, full, head, context)
                if state in ("success", "failure", "error"):
                    continue
                if state == "pending" and not _stale(_pending_since(gh, full, head, context), max_pending_minutes):
                    continue
                out.append(Candidate(repo=full, sha=head, base=pr["base"]["sha"], ref=pr["head"]["ref"], event="pull_request",
                                     actor=(pr.get("user") or {}).get("login") or "unknown", pr_number=int(pr["number"]), default_branch=default_branch))
                if len(out) >= max_candidates:
                    return out
            # Direct pushes to the default branch and other long-lived branches.
            for branch in dict.fromkeys([default_branch, *extra_branches]):
                commits = gh.get(f"/repos/{full}/commits", {"sha": branch, "since": since, "per_page": 50}, ok404=True)
                if not commits or not isinstance(commits, list):
                    continue
                newest = commits[0]
                state = gate_state(gh, full, newest["sha"], context)
                if state in ("success", "failure", "error"):
                    continue
                if state == "pending" and not _stale(_pending_since(gh, full, newest["sha"], context), max_pending_minutes):
                    continue
                base = ""
                for older in commits[1:]:
                    if gate_state(gh, full, older["sha"], context) in ("success", "failure", "error"):
                        base = older["sha"]
                        break
                if not base:
                    parents = newest.get("parents") or []
                    base = parents[0]["sha"] if parents else ""
                actor = (newest.get("author") or {}).get("login") or (newest.get("committer") or {}).get("login") or "unknown"
                out.append(Candidate(repo=full, sha=newest["sha"], base=base, ref=branch, event="push", actor=actor, default_branch=default_branch))
                if len(out) >= max_candidates:
                    return out
    return out


def set_status(gh: GitHub, repo: str, sha: str, state: str, description: str, target_url: str = "", context: str = STATUS_CONTEXT) -> None:
    if not REPO_RE.match(repo):
        raise GitHubError(f"invalid repository slug {repo!r}")
    if state not in ("pending", "success", "failure", "error"):
        raise GitHubError(f"invalid status state {state!r}")
    body: dict[str, Any] = {"state": state, "context": context, "description": description[:140]}
    if target_url:
        body["target_url"] = target_url
    gh.post(f"/repos/{repo}/statuses/{sha}", body)
