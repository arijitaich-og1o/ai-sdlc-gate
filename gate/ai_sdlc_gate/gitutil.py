"""Thin wrappers around git. All calls use argument lists (no shell)."""
from __future__ import annotations

import subprocess
from pathlib import Path

ZERO_SHA = "0000000000000000000000000000000000000000"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitError(RuntimeError):
    pass


def run_git(args: list[str], cwd: str | Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def repo_root(cwd: str | Path | None = None) -> Path:
    return Path(run_git(["rev-parse", "--show-toplevel"], cwd=cwd).strip())


def current_branch(cwd: str | Path | None = None) -> str:
    out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, check=False).strip()
    return out or "HEAD"


def head_author(cwd: str | Path | None = None) -> tuple[str, str]:
    out = run_git(["log", "-1", "--format=%an%x00%ae"], cwd=cwd, check=False).strip()
    if not out:
        return ("", "")
    name, _, email = out.partition("\x00")
    return (name, email)


def rev_exists(rev: str, cwd: str | Path | None = None) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", rev],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def resolve_base(base: str | None, head: str, cwd: str | Path | None = None) -> str | None:
    """Return a usable base revision; falls back to head's parent or None (root commit)."""
    if base and base != ZERO_SHA and rev_exists(base, cwd):
        return base
    if rev_exists(f"{head}~1", cwd):
        return f"{head}~1"
    return None


def commit_messages(base: str | None, head: str, cwd: str | Path | None = None) -> list[str]:
    rng = f"{base}..{head}" if base else head
    out = run_git(["log", "--format=%B%x1e", rng], cwd=cwd, check=False)
    return [m.strip() for m in out.split("\x1e") if m.strip()]


def _parse_name_status(out: str) -> list[tuple[str, str]]:
    # NUL-delimited (`-z`) parsing: with --no-renames the stream is status\0path\0status\0path...
    # so filenames containing tabs, spaces, quotes or newlines are handled without corruption or
    # path-truncation that could hide a file from the deterministic secret prechecks.
    rows: list[tuple[str, str]] = []
    fields = [f for f in out.split("\x00")]
    i = 0
    while i < len(fields):
        status = fields[i].strip()
        if not status:
            i += 1
            continue
        if i + 1 >= len(fields):
            break
        path = fields[i + 1]
        rows.append((status[:1], path))
        i += 2
    return rows


def name_status(base: str | None, head: str, cwd: str | Path | None = None) -> list[tuple[str, str]]:
    args = ["diff", "--name-status", "--no-renames", "-z"]
    args.extend([base, head] if base else [EMPTY_TREE, head])
    return _parse_name_status(run_git(args, cwd=cwd))


def staged_name_status(cwd: str | Path | None = None) -> list[tuple[str, str]]:
    return _parse_name_status(run_git(["diff", "--cached", "--name-status", "--no-renames", "-z"], cwd=cwd))


def file_diff(path: str, base: str | None, head: str, cwd: str | Path | None = None, staged: bool = False) -> str:
    if staged:
        return run_git(["diff", "--cached", "--unified=3", "--", path], cwd=cwd, check=False)
    left = base or EMPTY_TREE
    return run_git(["diff", "--unified=3", left, head, "--", path], cwd=cwd, check=False)


def file_at(rev: str, path: str, cwd: str | Path | None = None) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else None


def staged_file(path: str, cwd: str | Path | None = None) -> str | None:
    return file_at(":", path, cwd)
