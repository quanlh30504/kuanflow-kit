"""Contract tests C43: kuanflow_cli.patchers.gitignore."""

from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

BEGIN = "# kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here)"
END = "# kuanflow:end"
IDENTITY = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


@pytest.fixture
def gi() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.gitignore")


@pytest.fixture
def mb() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.managed_block")


@pytest.fixture(autouse=True)
def _clean_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Inherited GIT_* (e.g. GIT_DIR from a hook) must not leak into the code under test either.
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)


def git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {**env, **IDENTITY, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=git_env(),
        timeout=60,
    )
    return proc.stdout.strip()


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "init")
    return path


# --- exclude_path -------------------------------------------------------------------------------


def test_c43_exclude_path_normal_repo(gi: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    got = gi.exclude_path(repo)
    assert isinstance(got, Path)
    assert got.resolve() == (repo / ".git" / "info" / "exclude").resolve()


def test_c43_exclude_path_from_subdirectory(
    gi: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path / "repo")
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)  # cwd elsewhere: the result must be resolved against the given dir
    got = gi.exclude_path(sub)
    assert got.resolve() == (repo / ".git" / "info" / "exclude").resolve()


def test_c43_exclude_path_linked_worktree_uses_common_dir(
    gi: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feature", str(wt))
    monkeypatch.chdir(tmp_path)
    expected = (repo / ".git" / "info" / "exclude").resolve()
    assert gi.exclude_path(wt).resolve() == expected
    sub = wt / "deep"
    sub.mkdir()
    assert gi.exclude_path(sub).resolve() == expected


def test_c43_exclude_path_matches_git(gi: ModuleType, tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "other", str(wt))
    raw = git(wt, "rev-parse", "--git-path", "info/exclude")
    assert gi.exclude_path(wt).resolve() == (wt / raw).resolve()


# --- wrappers -----------------------------------------------------------------------------------


def test_c43_upsert_uses_hash_style_at_bottom(gi: ModuleType, mb: ModuleType) -> None:
    text = "*.pyc\n"
    out = gi.upsert(text, ".kuanflow/cache/\n")
    assert out == f"*.pyc\n\n{BEGIN}\n.kuanflow/cache/\n{END}\n"
    assert out == mb.upsert(text, ".kuanflow/cache/\n", "hash", "bottom")
    assert gi.upsert(None, "x") == f"{BEGIN}\nx\n{END}\n"
    assert gi.upsert("no newline", "x") == f"no newline\n\n{BEGIN}\nx\n{END}\n"


def test_c43_upsert_replaces_existing_block(gi: ModuleType) -> None:
    text = f"top\n{BEGIN}\nold\n{END}\nbottom\n"
    assert gi.upsert(text, "new") == f"top\n{BEGIN}\nnew\n{END}\nbottom\n"


def test_c43_remove_uses_hash_style(gi: ModuleType, mb: ModuleType) -> None:
    text = f"*.pyc\n\n{BEGIN}\nx\n{END}\n"
    assert gi.remove(text) == "*.pyc\n"
    assert gi.remove(text) == mb.remove(text, "hash")
    html = "<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->\nx\n"
    html += "<!-- kuanflow:end -->\n"
    assert gi.remove(html) == html


def test_c43_round_trip(gi: ModuleType) -> None:
    for text in ("", "*.pyc\n", "a\n\nb\n\n"):
        assert gi.remove(gi.upsert(text, "x\ny")) == text
