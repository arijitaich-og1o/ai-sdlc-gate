"""Collecting the set of changes the gate should review."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import gitutil
from .config import Config

DEFAULT_EXCLUDES = [
    "**/*.lock",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/poetry.lock",
    "**/Cargo.lock",
    "**/go.sum",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",
    "**/dist/**",
    "**/build/**",
    "**/node_modules/**",
    "**/vendor/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg",
    "**/*.gif",
    "**/*.ico",
    "**/*.pdf",
    "**/*.woff",
    "**/*.woff2",
    "**/*.ttf",
    "**/*.zip",
    "**/*.jar",
    "**/*.so",
    "**/*.dll",
    "**/*.exe",
]


@dataclass
class ChangedFile:
    path: str
    status: str  # A, M, D, R, C, T
    diff: str = ""
    content: str | None = None
    truncated: bool = False
    binary: bool = False

    @property
    def size(self) -> int:
        return len(self.diff) + len(self.content or "")


@dataclass
class ChangeSet:
    files: list[ChangedFile] = field(default_factory=list)
    commit_messages: list[str] = field(default_factory=list)
    branch: str = ""
    author_name: str = ""
    author_email: str = ""
    base: str | None = None
    head: str = ""
    mode: str = "range"
    excluded: list[str] = field(default_factory=list)

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.files]

    @property
    def total_bytes(self) -> int:
        return sum(f.size for f in self.files)


def matches_any(path: str, globs: list[str]) -> bool:
    p = PurePosixPath(path).as_posix()
    for g in globs:
        if fnmatch.fnmatch(p, g):
            return True
        # `**/dist/**` should also match `dist/x` at the repo root
        if g.startswith("**/") and fnmatch.fnmatch(p, g[3:]):
            return True
    return False


def _is_binary(text: str | None) -> bool:
    if text is None:
        return False
    return "\x00" in text[:4096]


def _truncate(text: str | None, limit: int) -> tuple[str | None, bool]:
    if text is None or len(text) <= limit:
        return text, False
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars by ai-sdlc-gate]\n", True


def collect_range(cfg: Config, base: str | None, head: str, cwd: Path | None = None) -> ChangeSet:
    base = gitutil.resolve_base(base, head, cwd)
    rows = gitutil.name_status(base, head, cwd)
    cs = ChangeSet(base=base, head=head, mode="range", branch=gitutil.current_branch(cwd))
    cs.author_name, cs.author_email = gitutil.head_author(cwd)
    cs.commit_messages = gitutil.commit_messages(base, head, cwd)
    _fill(cfg, cs, rows, lambda p: gitutil.file_diff(p, base, head, cwd), lambda p: gitutil.file_at(head, p, cwd))
    return cs


def collect_staged(cfg: Config, cwd: Path | None = None) -> ChangeSet:
    rows = gitutil.staged_name_status(cwd)
    cs = ChangeSet(base="HEAD", head="INDEX", mode="staged", branch=gitutil.current_branch(cwd))
    cs.author_name, cs.author_email = gitutil.head_author(cwd)
    _fill(cfg, cs, rows, lambda p: gitutil.file_diff(p, None, "", cwd, staged=True), lambda p: gitutil.staged_file(p, cwd))
    return cs


def collect_paths(cfg: Config, paths: list[str], root: Path) -> ChangeSet:
    """Review whole files (used for trials evaluation and ad-hoc scans)."""
    cs = ChangeSet(mode="paths", head="WORKTREE")
    root = root.resolve()
    rows: list[tuple[str, str]] = []
    for raw in paths:
        p = Path(raw) if Path(raw).is_absolute() else (root / raw)
        p = p.resolve()
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not any(part.startswith(".") for part in f.relative_to(root).parts):
                    rows.append(("A", f.relative_to(root).as_posix()))
        elif p.is_file():
            rel = p.relative_to(root).as_posix() if p.is_relative_to(root) else p.as_posix()
            rows.append(("A", rel))

    def read(path: str) -> str | None:
        fp = root / path if not Path(path).is_absolute() else Path(path)
        try:
            return fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    _fill(cfg, cs, rows, lambda p: "", read)
    return cs


def _fill(cfg: Config, cs: ChangeSet, rows, diff_fn, content_fn) -> None:
    excludes = DEFAULT_EXCLUDES + list(cfg.gate.get("exclude_globs") or [])
    max_file = int(cfg.gate.get("max_file_bytes", 120_000))
    for status, path in rows:
        if matches_any(path, excludes):
            cs.excluded.append(path)
            continue
        cf = ChangedFile(path=path, status=status)
        if status != "D":
            content = content_fn(path)
            if _is_binary(content):
                cf.binary = True
                cs.files.append(cf)
                continue
            cf.content, t1 = _truncate(content, max_file)
        else:
            t1 = False
        diff = diff_fn(path)
        cf.diff, t2 = _truncate(diff, max_file)
        cf.truncated = t1 or t2
        cs.files.append(cf)


def render_changeset(cs: ChangeSet, include_full_content: bool = True, budget: int | None = None) -> str:
    """Render the change set for the model, with each file fenced in explicit delimiters."""
    parts: list[str] = []
    if cs.commit_messages:
        parts.append("<commit_messages>\n" + "\n---\n".join(cs.commit_messages) + "\n</commit_messages>")
    used = sum(len(p) for p in parts)
    for f in cs.files:
        attrs = f' binary="true"' if f.binary else ""
        block = [f'<file path="{f.path}" status="{f.status}"{attrs}>']
        if f.binary:
            block.append("[binary file omitted]")
        else:
            if f.diff:
                block.append("<diff>\n" + f.diff.rstrip() + "\n</diff>")
            if include_full_content and f.content is not None and f.status != "D":
                block.append("<content_after_change>\n" + f.content.rstrip() + "\n</content_after_change>")
        block.append("</file>")
        text = "\n".join(block)
        if budget is not None and used + len(text) > budget:
            parts.append(f'<file path="{f.path}" status="{f.status}">[omitted: change set exceeded review budget]</file>')
            continue
        used += len(text)
        parts.append(text)
    return "\n\n".join(parts)


def _empty_like(cs: ChangeSet) -> ChangeSet:
    return ChangeSet(
        commit_messages=cs.commit_messages,
        branch=cs.branch,
        base=cs.base,
        head=cs.head,
        mode=cs.mode,
        author_name=cs.author_name,
        author_email=cs.author_email,
    )


def chunk_changeset(cs: ChangeSet, max_bytes: int) -> list[ChangeSet]:
    """Split a change set into chunks that fit the review budget (by file)."""
    chunks: list[ChangeSet] = []
    current = _empty_like(cs)
    size = 0
    for f in cs.files:
        fsize = f.size + 200
        if current.files and size + fsize > max_bytes:
            chunks.append(current)
            current = _empty_like(cs)
            size = 0
        current.files.append(f)
        size += fsize
    if current.files or not chunks:
        chunks.append(current)
    return chunks
