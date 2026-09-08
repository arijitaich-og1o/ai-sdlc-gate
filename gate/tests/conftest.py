from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sdlc_gate.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def cfg() -> Config:
    return Config.load(REPO_ROOT / "gate.config.yaml")


@pytest.fixture(scope="session")
def skills_dir() -> Path:
    return REPO_ROOT / "skills"


@pytest.fixture(scope="session")
def demo_root() -> Path:
    return REPO_ROOT / "demo_codebase"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with one initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "dev@example.com", cwd=repo)
    git("config", "user.name", "Dev", cwd=repo)
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "initial", cwd=repo)
    return repo
