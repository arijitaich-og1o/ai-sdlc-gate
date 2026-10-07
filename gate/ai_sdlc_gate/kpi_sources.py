"""Measured data streams for the KPIs beyond the gate's own events: git history and GitHub pull requests.

Both collectors keep metadata only. Commit authors are pseudonymised with a one-way hash, used solely to count
distinct people per team; no name, e-mail, commit message or code is kept. Classification rules (what counts as a
revert or a fix commit) are fixed here and documented in docs/kpi/README.md, so the numbers are reproducible.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from typing import Any, Callable, Iterable

from . import gitutil

# A revert is what `git revert` writes; a fix commit follows the Conventional Commits `fix:` / `hotfix:` type.
REVERT_RE = re.compile(r'^Revert "|This reverts commit [0-9a-f]{7,40}', re.MULTILINE)
FIX_RE = re.compile(r"^(?:fix|hotfix|bugfix)(?:\([^)]*\))?!?:", re.IGNORECASE)


def person_salt(home: Path) -> str:
    """This machine's secret key for pseudonymising people, created once (`<gate home>/kpi-salt`).

    A plain hash of an e-mail can be reversed by hashing a list of likely addresses; a keyed hash cannot without
    the key. Collect and export on the same machine so git and gate keys match for coverage.
    """
    path = home / "kpi-salt"
    if path.is_file():
        salt = path.read_text(encoding="utf-8").strip()
        if salt:
            return salt
    home.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    path.write_text(salt, encoding="utf-8")
    return salt


def subkey(salt: str, purpose: str) -> bytes:
    """A key for one purpose only, derived from the machine secret (HMAC-SHA256 as the derivation function).

    Internal person keys and published team pseudonyms use different sub-keys, so outputs published for one purpose
    never share a key with the other.
    """
    if not salt:
        raise ValueError("a salt is required to pseudonymise")
    return hmac.new(salt.encode("utf-8"), b"ai-sdlc-gate/kpi/" + purpose.encode("utf-8"), hashlib.sha256).digest()


def person_key(email: str, salt: str) -> str:
    """Pseudonymous, stable key for counting distinct people: keyed HMAC-SHA256, not reversible without `salt`."""
    return hmac.new(subkey(salt, "person-keys"), (email or "").strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def read_jsonl(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: str | Path) -> None:
    Path(path).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")


# ----------------------------------------------------------------------------- git history

def collect_git(repo_dir: str | Path, salt: str, slug: str | None = None, ref: str = "HEAD", since: str | None = None) -> list[dict[str, Any]]:
    """One row per commit reachable from `ref` (the default branch, normally): time, author key, merge/revert/fix."""
    slug = slug or gitutil.repo_slug(repo_dir)
    args = ["log", ref, "--no-color", "--format=%H%x1f%cI%x1f%ae%x1f%P%x1f%s%x1f%b%x1e"]
    if since:
        args.append(f"--since={since}")
    out = gitutil.run_git(args, cwd=repo_dir)
    rows = []
    for rec in out.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) < 6:
            continue
        sha, ts, email, parents, subject, body = parts[:6]
        rows.append({
            "repo": slug,
            "sha": sha[:12],
            "ts": ts,
            "author": person_key(email, salt),
            "merge": len(parents.split()) > 1,
            "revert": bool(REVERT_RE.search(subject + "\n" + body)),
            "fix": bool(FIX_RE.match(subject.strip())),
        })
    rows.sort(key=lambda r: (r["ts"], r["sha"]))
    return rows


# ----------------------------------------------------------------------------- pull requests

# A fetch takes an API path and returns the decoded JSON body, or raises on any failure (HTTP error, empty or
# undecodable output). It never returns None to signal an error. Callers still check the shape they expect,
# because a successful response can be an error object, e.g. {"message": "Bad credentials"}.
Fetch = Callable[[str], Any]


def github_fetch(token: str, api: str = "https://api.github.com") -> Fetch:
    import httpx

    from .httpcfg import ssl_context

    client = httpx.Client(
        base_url=api, timeout=30, verify=ssl_context(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ai-sdlc-gate-kpi/1.0"},
    )

    def fetch(path: str) -> Any:
        resp = client.get(path)
        resp.raise_for_status()
        return resp.json()

    fetch.close = client.close  # type: ignore[attr-defined]  # the caller closes the connection pool when done
    return fetch


def gh_fetch(gh: str = "gh") -> Fetch:
    """Read the GitHub API through the GitHub CLI's own sign-in: no token is read or handled here."""
    import subprocess

    def fetch(path: str) -> Any:
        # gh writes UTF-8 whatever the platform. Decoding with the locale (cp1252 on Windows) failed on non-ASCII
        # PR bodies inside subprocess's reader thread, left stdout as None and made a repository read as "0 PRs".
        out = subprocess.run([gh, "api", path], capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        if out.returncode != 0:
            raise RuntimeError(f"gh api {path.split('?')[0]} failed: {(out.stderr or '').strip()[:200]}")
        if not (out.stdout or "").strip():
            raise RuntimeError(f"gh api {path.split('?')[0]} returned no output")
        return json.loads(out.stdout)

    return fetch


def collect_prs(slug: str, fetch: Fetch, max_prs: int = 200) -> list[dict[str, Any]]:
    """One row per closed pull request (newest first, up to `max_prs`): open/merge times, review effort, revert."""
    # GitHub owners are letters, digits and hyphens; repository names may also use `.` and `_`.
    if not re.match(r"^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$", slug):
        raise ValueError(f"invalid repository slug: {slug!r}")
    pulls: list[dict[str, Any]] = []
    page = 1
    while len(pulls) < max_prs:
        batch = fetch(f"/repos/{slug}/pulls?state=closed&per_page=100&sort=created&direction=desc&page={page}")
        # Only an empty list means "no more pull requests"; anything else is a failed read that must not pass as
        # a repository without PRs (the KPI would silently show 0).
        if not isinstance(batch, list):
            raise RuntimeError(f"unexpected response for pull requests of {slug} (page {page}): {type(batch).__name__}")
        if not batch:
            break
        pulls.extend(batch)
        page += 1
    rows = []
    for p in pulls[:max_prs]:
        row = {
            "repo": slug,
            "number": int(p["number"]),
            "created_at": p["created_at"],
            "merged_at": p.get("merged_at"),
            "revert": str(p.get("title") or "").startswith("Revert "),
            "reviews": None,
            "changes_requested": None,
            "review_comments": None,
        }
        if row["merged_at"]:
            detail = fetch(f"/repos/{slug}/pulls/{row['number']}")
            reviews = fetch(f"/repos/{slug}/pulls/{row['number']}/reviews?per_page=100")
            submitted = [r for r in reviews if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED")]
            row.update({
                "reviews": len(submitted),
                "changes_requested": sum(1 for r in submitted if r.get("state") == "CHANGES_REQUESTED"),
                "review_comments": int(detail.get("review_comments") or 0),
            })
        rows.append(row)
    rows.sort(key=lambda r: (r["created_at"], r["number"]))
    return rows
