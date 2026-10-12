"""Contract tests C37 (and the git part of C36d): kuanflow_cli.root (git_toplevel, find_root)."""

from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def root_mod() -> ModuleType:
    return importlib.import_module("kuanflow_cli.root")


def root_error() -> type[Exception]:
    return importlib.import_module("kuanflow_cli.errors").RootError


def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Kuanflow Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Kuanflow Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(path), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
        env=_git_env(),
    )
    return path


def manifest(dir_: Path) -> Path:
    p = dir_ / ".kuanflow" / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n", encoding="utf-8")
    return dir_


@pytest.fixture(autouse=True)
def _clean_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A directory that is not inside any git work tree (guards the premise of the tests)."""
    d = tmp_path / "outside"
    d.mkdir()
    proc = subprocess.run(
        ["git", "-C", str(d), "rev-parse", "--show-toplevel"],
        capture_output=True,
        env=_git_env(),
    )
    if proc.returncode == 0:
        pytest.skip("tmp_path is inside a git work tree")
    return d


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return git_init(tmp_path / "repo")


# --- git_toplevel -------------------------------------------------------------------------------


def test_git_toplevel_at_root(repo: Path) -> None:
    assert root_mod().git_toplevel(repo) == repo.resolve()


def test_git_toplevel_from_subdir(repo: Path) -> None:
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    got = root_mod().git_toplevel(sub)
    assert isinstance(got, Path)
    assert got == repo.resolve()


def test_git_toplevel_is_resolved(tmp_path: Path, repo: Path) -> None:
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    assert root_mod().git_toplevel(link) == repo.resolve()


def test_git_toplevel_none_outside_repo(outside: Path) -> None:
    assert root_mod().git_toplevel(outside) is None


def test_git_toplevel_ignores_inherited_git_dir(
    tmp_path: Path, repo: Path, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = git_init(tmp_path / "other")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    sub = repo / "sub"
    sub.mkdir()
    mod = root_mod()
    assert mod.git_toplevel(sub) == repo.resolve()
    assert mod.git_toplevel(outside) is None


# --- find_root: explicit ------------------------------------------------------------------------


def test_explicit_root_ok(repo: Path) -> None:
    sub = repo / "services" / "a"
    sub.mkdir(parents=True)
    manifest(repo)  # a manifest above does not matter for an explicit root
    assert root_mod().find_root(repo, explicit=sub) == sub.resolve()


def test_explicit_root_relative_is_resolved(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = repo / "svc"
    sub.mkdir()
    monkeypatch.chdir(repo)
    assert root_mod().find_root(Path("."), explicit=Path("svc")) == sub.resolve()


def test_explicit_root_missing(repo: Path) -> None:
    with pytest.raises(root_error()):
        root_mod().find_root(repo, explicit=repo / "nope")


def test_explicit_root_is_a_file(repo: Path) -> None:
    f = repo / "file.txt"
    f.write_text("x\n", encoding="utf-8")
    with pytest.raises(root_error()):
        root_mod().find_root(repo, explicit=f)


def test_explicit_root_not_git(repo: Path, outside: Path) -> None:
    with pytest.raises(root_error()):
        root_mod().find_root(repo, explicit=outside)


# --- find_root: walk-up -------------------------------------------------------------------------


def test_no_manifest_returns_toplevel(repo: Path) -> None:
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    assert root_mod().find_root(sub) == repo.resolve()
    assert root_mod().find_root(repo) == repo.resolve()


def test_manifest_at_toplevel_found_from_subdir(repo: Path) -> None:
    manifest(repo)
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    assert root_mod().find_root(sub) == repo.resolve()


def test_walk_up_finds_nearest_manifest(repo: Path) -> None:
    manifest(repo)
    svc = manifest(repo / "services" / "a")
    deep = svc / "src" / "x"
    deep.mkdir(parents=True)
    mod = root_mod()
    assert mod.find_root(deep) == svc.resolve()
    assert mod.find_root(svc) == svc.resolve()
    other = repo / "services" / "b"
    other.mkdir(parents=True)
    assert mod.find_root(other) == repo.resolve()


def test_kuanflow_dir_without_manifest_ignored(repo: Path) -> None:
    svc = repo / "services" / "a"
    (svc / ".kuanflow").mkdir(parents=True)
    (svc / ".kuanflow" / "config.yaml").write_text("x: 1\n", encoding="utf-8")
    assert root_mod().find_root(svc) == repo.resolve()


def test_manifest_must_be_a_file(repo: Path) -> None:
    svc = repo / "services" / "a"
    (svc / ".kuanflow" / "manifest.json").mkdir(parents=True)
    assert root_mod().find_root(svc) == repo.resolve()


def test_never_above_toplevel(tmp_path: Path) -> None:
    outer = manifest(tmp_path / "outer")  # e.g. ~/.kuanflow/manifest.json above the repo
    repo = git_init(outer / "repo")
    sub = repo / "sub"
    sub.mkdir()
    assert root_mod().find_root(sub) == repo.resolve()


def test_start_is_resolved(tmp_path: Path, repo: Path) -> None:
    svc = manifest(repo / "svc")
    link = tmp_path / "link"
    link.symlink_to(svc, target_is_directory=True)
    assert root_mod().find_root(link) == svc.resolve()


def test_not_a_git_repo(outside: Path) -> None:
    manifest(outside)
    with pytest.raises(root_error(), match="not inside a git repository"):
        root_mod().find_root(outside)


def test_find_root_ignores_inherited_git_dir(
    tmp_path: Path, repo: Path, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = git_init(tmp_path / "other")
    manifest(other)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    sub = repo / "sub"
    sub.mkdir()
    mod = root_mod()
    assert mod.find_root(sub) == repo.resolve()
    with pytest.raises(root_error()):
        mod.find_root(outside)
