"""Contract tests C37 via the CLI (CMD-23, Q-34) and the ADR-0002 `_src_path` TODO."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    assert_error,
    assert_ok,
    build,
    commit_all,
    describe,
    git,
    invoke,
    read_answers,
    read_config,
    read_manifest,
    write,
)

SRC_PATH = ".kuanflow/cache/template-repo"
PNPM = {
    "test_cmd": "pnpm test",
    "single_test_cmd": "pnpm test -- {test}",
    "build_cmd": "pnpm run build",
    "lint_cmd": "pnpm run lint",
    "verify_cmd": "pnpm test",
}


def test_init_from_subdir_installs_at_toplevel(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    sub = root / "src/main/java"
    result = invoke(["init", "--yes"], cwd=sub)
    assert_ok(result)
    assert (root / ".kuanflow/manifest.json").is_file()
    assert not (sub / ".kuanflow").exists()
    answers = read_answers(root)
    assert answers["_src_path"] == SRC_PATH  # relative, even from a sub-directory (ADR-0002)
    assert answers["project_name"] == "maven"
    assert answers["stack"] == "java-maven"
    assert "create .kuanflow/README.md" in result.stdout.splitlines()  # root-relative paths


@pytest.fixture
def monorepo_web(tmp_path: Path, env: pytest.MonkeyPatch) -> Path:
    top = build("monorepo", tmp_path / "monorepo")
    result = invoke(["init", "--yes", "--root", "services/web"], cwd=top)
    assert_ok(result)
    assert "create .kuanflow/README.md" in result.stdout.splitlines()
    commit_all(top, "kuanflow init web")
    return top


def test_monorepo_root_option(monorepo_web: Path) -> None:
    top = monorepo_web
    web = top / "services/web"
    assert (web / ".kuanflow/manifest.json").is_file()
    assert not (top / ".kuanflow").exists()
    assert not (top / "AGENTS.md").exists()
    assert (web / "AGENTS.md").is_file()
    answers = read_answers(web)
    assert answers["_src_path"] == SRC_PATH
    assert answers["project_name"] == "web"
    assert answers["stack"] == "node"
    for key, value in PNPM.items():
        assert answers[key] == value, key
    assert read_config(web)["commands"]["build"] == "pnpm run build"
    assert read_manifest(web)["mode"] == "project"


def test_status_from_deep_inside_service(monorepo_web: Path) -> None:
    top = monorepo_web
    deep = top / "services/web/src/components/deep"
    deep.mkdir(parents=True)
    result = invoke(["status"], cwd=deep)
    assert_ok(result)
    assert result.stdout.splitlines()[-1] == "All managed files match the manifest."
    # From the toplevel there is no manifest on the way up: not installed.
    assert_error(invoke(["status"], cwd=top))
    # --root overrides the walk.
    assert_ok(invoke(["status", "--root", "services/web"], cwd=top))
    assert_error(invoke(["status", "--root", "../order-svc"], cwd=top / "services/web"))


def test_root_dir_without_manifest_does_not_count(monorepo_web: Path) -> None:
    top = monorepo_web
    order = top / "services/order-svc"
    (order / ".kuanflow").mkdir()
    write(order, ".kuanflow/config.yaml", "schema_version: 1\n")
    assert_error(invoke(["status"], cwd=order))


def test_monorepo_clean_check_limited_to_root(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    write(top, "services/order-svc/wip.txt", "wip\n")
    write(top, "README.md", "edited\n")
    assert_ok(invoke(["init", "--yes", "--root", "services/web"], cwd=top))
    git(top, "add", "services/web")
    git(top, "commit", "-q", "--no-verify", "-m", "kuanflow init web")
    write(top, "services/web/wip.txt", "wip\n")
    dirty = invoke(["uninstall", "--root", "services/web"], cwd=top)
    assert_error(dirty, "wip.txt")
    assert "order-svc" not in dirty.stderr and "README.md" not in dirty.stderr
    (top / "services/web/wip.txt").unlink()
    assert_ok(invoke(["uninstall", "--root", "services/web"], cwd=top))
    assert not (top / "services/web/.kuanflow/manifest.json").exists()


def test_monorepo_detection_reads_only_root(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    result = invoke(["init", "--yes", "--root", "services/order-svc"], cwd=top)
    assert_ok(result)
    answers = read_answers(top / "services/order-svc")
    assert answers["stack"] == "java-maven"
    assert answers["verify_cmd"] == "./mvnw -q verify"
    assert answers["protected_paths"] == ["**/legacy/**"]


def test_cwd_inside_service_without_root_uses_toplevel(
    tmp_path: Path, env: pytest.MonkeyPatch
) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    assert_ok(invoke(["init", "--yes"], cwd=top / "services/web"))
    assert (top / ".kuanflow/manifest.json").is_file()
    assert not (top / "services/web/.kuanflow").exists()
    assert read_answers(top)["project_name"] == "monorepo"


@pytest.mark.parametrize("bad", ["does-not-exist", "README.md"])
def test_root_option_must_be_existing_dir(
    tmp_path: Path, env: pytest.MonkeyPatch, bad: str
) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    assert_error(invoke(["init", "--yes", "--root", bad], cwd=top))
    assert not (top / ".kuanflow").exists()


def test_root_option_outside_git(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    plain = tmp_path / "plain"
    plain.mkdir()
    result = invoke(["init", "--yes", "--root", str(plain)], cwd=top)
    assert_error(result)
    assert list(plain.iterdir()) == [], describe(result)
