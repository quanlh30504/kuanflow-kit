"""Contract tests C23, C24, C25: kuanflow_cli.engine (content_root, assemble_template, render)."""

from __future__ import annotations

import importlib
import inspect
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE = ".kuanflow/cache/template-repo"

COPIER_YML = """\
_subdirectory: template
_templates_suffix: .jinja
name:
  type: str
  default: dflt
kuanflow_version:
  type: str
  default: ""
"""
ANSWERS_TEMPLATE = "{{ _copier_answers|to_nice_yaml }}"


def engine() -> ModuleType:
    return importlib.import_module("kuanflow_cli.engine")


def write(root: Path, rel: str, text: str, mode: int | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mode is not None:
        p.chmod(mode)
    return p


def make_source(
    root: Path,
    *,
    template: str = "project",
    marker: str = "one",
    extra: dict[str, str] | None = None,
    copier_yml: str = COPIER_YML,
    scripts: dict[str, str] | None = None,
) -> Path:
    """A fake content root with the C23 layout."""
    write(root, "VERSION", "0.0.0\n")
    write(root, f"templates/{template}/copier.yml", copier_yml)
    write(
        root,
        f"templates/{template}/template/{{{{ _copier_conf.answers_file }}}}.jinja",
        ANSWERS_TEMPLATE,
    )
    write(
        root, f"templates/{template}/template/out.txt.jinja", "{{ name }} {{ kuanflow_version }}\n"
    )
    write(root, f"templates/{template}/template/marker.txt", f"{marker}\n")
    for rel, text in (extra or {}).items():
        write(root, f"templates/{template}/{rel}", text)
    for name, text in (scripts if scripts is not None else {"x.sh": "#!/bin/sh\necho x\n"}).items():
        write(root, f"plugins/kuanflow/scripts/{name}", text, mode=0o644)
    return root


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=60,
    )
    return proc.stdout.strip()


def ls_tree(repo: Path, ref: str = "HEAD") -> dict[str, str]:
    out = {}
    for line in git(repo, "ls-tree", "-r", ref).splitlines():
        meta, path = line.split("\t", 1)
        out[path] = meta.split()[0]
    return out


# --- C23 content_root / current_version -------------------------------------------------------


def test_c23_content_root_is_repo_in_source_tree() -> None:
    root = engine().content_root()
    assert isinstance(root, Path)
    assert root.resolve() == REPO_ROOT.resolve()
    assert (root / "templates" / "project" / "copier.yml").is_file()


def test_c23_current_version() -> None:
    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert engine().current_version() == expected


# --- C24 assemble_template --------------------------------------------------------------------


def test_c24_single_version(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = tmp_path / "repo"
    assert Path(engine().assemble_template(dest, [("0.1.0", src)])) == dest
    assert git(dest, "tag", "--list") == "v0.1.0"
    assert git(dest, "describe", "--tags") == "v0.1.0"
    files = ls_tree(dest)
    assert "copier.yml" in files
    assert "template/out.txt.jinja" in files
    assert "template/marker.txt" in files
    assert files["template/.kuanflow/scripts/x.sh"] == "100755"


def test_c24_scripts_mode_0755_and_identical(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1", scripts={"x.sh": "#!/bin/sh\necho x\n", "y.sh": "y\n"})
    assert not os.access(src / "plugins/kuanflow/scripts/x.sh", os.X_OK)
    dest = engine().assemble_template(tmp_path / "repo", [("0.1.0", src)])
    files = ls_tree(Path(dest))
    for name in ["x.sh", "y.sh"]:
        rel = f"template/.kuanflow/scripts/{name}"
        assert files[rel] == "100755", rel
        wt = Path(dest) / rel
        assert stat.S_IMODE(wt.stat().st_mode) == 0o755
        assert wt.read_bytes() == (src / "plugins/kuanflow/scripts" / name).read_bytes()


def test_c24_knowledge_template_gets_no_scripts(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1", template="knowledge-repo")
    dest = engine().assemble_template(
        tmp_path / "repo", [("0.1.0", src)], template="knowledge-repo"
    )
    files = ls_tree(Path(dest))
    assert "copier.yml" in files
    assert not any(p.startswith("template/.kuanflow/scripts/") for p in files), files


def test_c24_two_versions(tmp_path: Path) -> None:
    s1 = make_source(tmp_path / "s1", marker="one", extra={"template/old.txt": "old\n"})
    s2 = make_source(tmp_path / "s2", marker="two")
    dest = Path(engine().assemble_template(tmp_path / "repo", [("0.1.0", s1), ("0.2.0", s2)]))
    assert sorted(git(dest, "tag", "--list").splitlines()) == ["v0.1.0", "v0.2.0"]
    assert git(dest, "describe", "--tags") == "v0.2.0"
    assert git(dest, "rev-list", "--count", "HEAD") == "2"
    assert git(dest, "rev-parse", "v0.2.0^{commit}") == git(dest, "rev-parse", "HEAD")
    assert git(dest, "show", "v0.1.0:template/marker.txt") == "one"
    assert git(dest, "show", "HEAD:template/marker.txt") == "two"
    assert "template/old.txt" in ls_tree(dest, "v0.1.0")
    assert "template/old.txt" not in ls_tree(dest)
    assert not (dest / "template" / "old.txt").exists()


def test_c24_commit_metadata(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = Path(engine().assemble_template(tmp_path / "repo", [("1.2.3-rc.1", src)]))
    fmt = "%an|%ae|%aI|%cn|%ce|%cI|%s"
    assert git(dest, "log", "-1", f"--format={fmt}") == (
        "kuanflow|kuanflow@localhost|2000-01-01T00:00:00+00:00|"
        "kuanflow|kuanflow@localhost|2000-01-01T00:00:00+00:00|kuanflow v1.2.3-rc.1"
    )
    # lightweight tag: the tag ref points directly at the commit
    assert git(dest, "cat-file", "-t", "v1.2.3-rc.1") == "commit"


def test_c24_reproducible_sha(tmp_path: Path) -> None:
    s1 = make_source(tmp_path / "s1", marker="one")
    s2 = make_source(tmp_path / "s2", marker="two")
    versions = [("0.1.0", s1), ("0.2.0", s2)]
    a = Path(engine().assemble_template(tmp_path / "a", versions))
    b = Path(engine().assemble_template(tmp_path / "b", versions))
    assert git(a, "rev-parse", "HEAD") == git(b, "rev-parse", "HEAD")
    assert git(a, "rev-parse", "v0.1.0") == git(b, "rev-parse", "v0.1.0")


def test_c24_prerelease_before_release_is_ascending(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    versions = [("1.0.0-dev", src), ("1.0.0-rc.1", src), ("1.0.0", src), ("1.0.1", src)]
    dest = Path(engine().assemble_template(tmp_path / "repo", versions))
    assert git(dest, "describe", "--tags") == "v1.0.1"
    assert len(git(dest, "tag", "--list").splitlines()) == 4


@pytest.mark.parametrize(
    "versions",
    [
        [],
        [("0.2.0", None), ("0.1.0", None)],
        [("0.1.0", None), ("0.1.0", None)],
        [("1.0.0", None), ("1.0.0-rc.1", None)],
        [("1.0", None)],
        [("v1.0.0", None)],
        [("1.0.0+build.1", None)],
        [("0.1.0", None), ("not-a-version", None)],
    ],
    ids=[
        "empty",
        "descending",
        "duplicate",
        "release-then-rc",
        "short",
        "v-prefix",
        "build",
        "bad",
    ],
)
def test_c24_invalid_versions(tmp_path: Path, versions: list[tuple[str, Any]]) -> None:
    src = make_source(tmp_path / "s1")
    versions = [(v, src) for v, _ in versions]
    dest = tmp_path / "repo"
    with pytest.raises(ValueError):
        engine().assemble_template(dest, versions)
    assert not dest.exists()


def test_c24_invalid_versions_leave_existing_dest(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = tmp_path / "repo"
    write(dest, "keep.txt", "keep\n")
    with pytest.raises(ValueError):
        engine().assemble_template(dest, [("0.2.0", src), ("0.1.0", src)])
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "keep\n"


def test_c24_unknown_template(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    with pytest.raises(ValueError):
        engine().assemble_template(tmp_path / "repo", [("0.1.0", src)], template="nope")


def test_c24_unknown_template_leaves_existing_dest(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = tmp_path / "repo"
    engine().assemble_template(dest, [("0.1.0", src)])
    head = git(dest, "rev-parse", "HEAD")
    write(dest, "keep.txt", "keep\n")
    with pytest.raises(ValueError):
        engine().assemble_template(dest, [("0.2.0", src)], template="nope")
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "keep\n"
    assert git(dest, "rev-parse", "HEAD") == head
    assert git(dest, "tag", "--list") == "v0.1.0"


def test_c24_dest_content_removed(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = tmp_path / "repo"
    write(dest, "junk.txt", "junk\n")
    write(dest, "deep/junk2.txt", "junk\n")
    engine().assemble_template(dest, [("0.1.0", src)])
    assert not (dest / "junk.txt").exists()
    assert not (dest / "deep").exists()
    assert "junk.txt" not in ls_tree(dest)


def test_c24_dest_existing_repo_replaced(tmp_path: Path) -> None:
    src = make_source(tmp_path / "s1")
    dest = tmp_path / "repo"
    engine().assemble_template(dest, [("0.1.0", src), ("0.2.0", src)])
    engine().assemble_template(dest, [("0.3.0", src)])
    assert git(dest, "tag", "--list") == "v0.3.0"
    assert git(dest, "rev-list", "--count", "HEAD") == "1"


def test_c24_user_global_git_config_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    hooks = home / "hooks"
    for hook in ["pre-commit", "commit-msg", "post-commit", "pre-auto-gc"]:
        write(hooks, hook, "#!/bin/sh\necho hook ran >&2\nexit 1\n", mode=0o755)
    write(home, "tpl/hooks/pre-commit", "#!/bin/sh\nexit 1\n", mode=0o755)
    gitconfig = write(
        home,
        ".gitconfig",
        "[user]\n\tname = Someone Else\n\temail = else@example.com\n"
        "[commit]\n\tgpgsign = true\n"
        "[tag]\n\tgpgsign = true\n"
        "[gpg]\n\tprogram = /bin/false\n"
        f"[core]\n\thooksPath = {hooks}\n"
        f"[init]\n\ttemplateDir = {home / 'tpl'}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.delenv("GIT_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)
    src = make_source(tmp_path / "s1")
    dest = Path(engine().assemble_template(tmp_path / "repo", [("0.1.0", src)]))
    assert git(dest, "log", "-1", "--format=%an|%ae") == "kuanflow|kuanflow@localhost"
    assert git(dest, "describe", "--tags") == "v0.1.0"


def _repo_state(repo: Path) -> tuple[str, str, str, str, bytes]:
    index = (repo / ".git" / "index").read_bytes()
    return (
        git(repo, "rev-parse", "HEAD"),
        git(repo, "tag", "--list"),
        git(repo, "for-each-ref"),
        git(repo, "status", "--porcelain", "--untracked-files=all"),
        index,
    )


def test_c24a_inherited_git_env_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    victim = tmp_path / "victim"
    write(victim, "a.txt", "a\n")
    git(victim, "init", "-q", "-b", "main")
    git(victim, "add", "a.txt")
    git(victim, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "victim")
    git(victim, "tag", "victim-tag")
    write(victim, "staged.txt", "s\n")
    git(victim, "add", "staged.txt")
    before = _repo_state(victim)
    monkeypatch.setenv("GIT_DIR", str(victim / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(victim))
    monkeypatch.setenv("GIT_INDEX_FILE", str(victim / ".git" / "index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(victim / ".git" / "objects"))
    monkeypatch.setenv("GIT_COMMON_DIR", str(victim / ".git"))
    src = make_source(tmp_path / "s1")
    dest = Path(engine().assemble_template(tmp_path / "repo", [("0.1.0", src), ("0.2.0", src)]))
    for key in [
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
    ]:
        monkeypatch.delenv(key)
    assert _repo_state(victim) == before
    assert (dest / ".git").is_dir()
    assert sorted(git(dest, "tag", "--list").splitlines()) == ["v0.1.0", "v0.2.0"]
    assert git(dest, "describe", "--tags") == "v0.2.0"
    assert "template/marker.txt" in ls_tree(dest)


# --- C25 render ------------------------------------------------------------------------------


def read_answers(dst: Path) -> dict[str, Any]:
    data = yaml.safe_load((dst / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_c25_render_basic(tmp_path: Path) -> None:
    content = make_source(tmp_path / "content")
    dst = tmp_path / "a" / "b" / "proj"
    data = {"name": "n1"}
    engine().render(dst, data, version="1.2.3", content=content)
    assert data == {"name": "n1"}, "caller's data must not be mutated"
    assert (dst / "out.txt").read_text(encoding="utf-8") == "n1 1.2.3\n"
    ans = read_answers(dst)
    assert ans["_src_path"] == CACHE
    assert ans["_commit"] == "v1.2.3"
    assert ans["name"] == "n1"
    assert ans["kuanflow_version"] == "1.2.3"
    cache = dst / CACHE
    assert git(cache, "describe", "--tags") == "v1.2.3"


def test_c25_caller_kuanflow_version_kept(tmp_path: Path) -> None:
    content = make_source(tmp_path / "content")
    dst = tmp_path / "proj"
    engine().render(
        dst, {"name": "n1", "kuanflow_version": "9.9.9"}, version="1.2.3", content=content
    )
    assert (dst / "out.txt").read_text(encoding="utf-8") == "n1 9.9.9\n"
    assert read_answers(dst)["kuanflow_version"] == "9.9.9"


def test_c25_version_defaults_to_current(tmp_path: Path) -> None:
    content = make_source(tmp_path / "content")
    dst = tmp_path / "proj"
    engine().render(dst, {"name": "n1"}, content=content)
    current = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    ans = read_answers(dst)
    assert ans["_commit"] == f"v{current}"
    assert ans["kuanflow_version"] == current


def test_c25_template_argument(tmp_path: Path) -> None:
    content = make_source(tmp_path / "content", template="knowledge-repo")
    dst = tmp_path / "proj"
    engine().render(dst, {"name": "k"}, version="0.1.0", content=content, template="knowledge-repo")
    assert (dst / "out.txt").read_text(encoding="utf-8") == "k 0.1.0\n"


def test_c25_cwd_restored_after_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = make_source(tmp_path / "content")
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.chdir(here)
    engine().render(tmp_path / "proj", {"name": "n1"}, version="1.0.0", content=content)
    assert Path.cwd() == here


def test_c25_copier_error_propagates_and_cwd_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import copier.errors

    content = make_source(
        tmp_path / "content", copier_yml='_min_copier_version: "99.0.0"\n' + COPIER_YML
    )
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.chdir(here)
    eng = engine()
    with pytest.raises(copier.errors.UnsupportedVersionError):
        eng.render(tmp_path / "proj", {"name": "n1"}, version="1.0.0", content=content)
    assert Path.cwd() == here


def test_c25_run_copy_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import copier

    eng = engine()
    real: Callable[..., Any] = copier.run_copy
    sig = inspect.signature(real)
    calls: list[tuple[dict[str, Any], Path]] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        calls.append((dict(bound.arguments), Path.cwd()))
        return real(*args, **kwargs)

    monkeypatch.setattr(copier, "run_copy", spy)
    if hasattr(eng, "run_copy"):
        monkeypatch.setattr(eng, "run_copy", spy)
    content = make_source(tmp_path / "content")
    dst = tmp_path / "proj"
    eng.render(dst, {"name": "n1"}, version="2.0.0", content=content)
    assert len(calls) == 1
    args, cwd = calls[0]
    assert cwd.resolve() == dst.resolve()
    assert str(args["src_path"]) == CACHE
    assert str(args.get("dst_path", ".")) == "."
    assert args["data"]["name"] == "n1"
    assert args["data"]["kuanflow_version"] == "2.0.0"
    assert args["defaults"] is True
    assert args["vcs_ref"] == "v2.0.0"
    assert args["quiet"] is True
    assert args.get("unsafe", False) is False
