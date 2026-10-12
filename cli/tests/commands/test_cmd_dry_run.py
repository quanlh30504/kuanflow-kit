"""Contract tests C47 step 6, C41 diff_text: `kuanflow init --dry-run` (PKG §12.5, TST-10)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import (
    FIXTURES,
    PROJECT_RENDERED,
    assert_ok,
    build,
    commit_all,
    describe,
    invoke,
    snapshot,
    write,
)

NEW_FILE = re.compile(r"^--- /dev/null\n\+\+\+ b/(.+)$", re.M)


@pytest.mark.parametrize("name", FIXTURES)
def test_dry_run_changes_nothing(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    root = build(name, tmp_path / name)
    before = snapshot(root)
    result = invoke(["init", "--dry-run"], cwd=root)
    assert_ok(result)
    assert snapshot(root) == before
    assert not (root / ".kuanflow").exists()
    out = result.stdout
    assert "+++ b/AGENTS.md" in out
    assert "+++ b/CLAUDE.md" in out
    assert "+++ b/.gitignore" in out
    assert "+++ b/.kuanflow/manifest.json" in out
    created = set(NEW_FILE.findall(out))
    assert PROJECT_RENDERED <= created, describe(result)
    assert ".kuanflow/manifest.json" in created
    assert "Apply? [y/N]" not in result.output  # --dry-run never prompts


def test_dry_run_existing_files_diffed_as_modifications(
    tmp_path: Path, env: pytest.MonkeyPatch
) -> None:
    root = build("maven", tmp_path / "maven")
    result = invoke(["init", "--dry-run"], cwd=root)
    assert_ok(result)
    out = result.stdout
    assert "--- a/CLAUDE.md\n+++ b/CLAUDE.md" in out
    assert "--- a/.gitignore\n+++ b/.gitignore" in out
    assert "--- /dev/null\n+++ b/AGENTS.md" in out
    assert "+<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->" in out
    assert '+  verify: "./mvnw -q verify"' in out
    # Existing CLAUDE.md lines appear as context, never as removals.
    assert "-# Order service" not in out


def test_dry_run_dirty_tree_only_warns(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, "scratch.txt", "wip\n")
    before = snapshot(root)
    result = invoke(["init", "--dry-run"], cwd=root)
    assert_ok(result)
    assert re.search(r"warn|not clean|dirty", result.output, re.I), describe(result)
    assert snapshot(root) == before


def test_dry_run_personal_no_exclude_change(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("gradle", tmp_path / "gradle")
    before = snapshot(root)
    result = invoke(["init", "--personal", "--dry-run"], cwd=root)
    assert_ok(result)
    assert snapshot(root) == before
    assert not (root / ".kuanflow").exists()


def test_dry_run_after_install_shows_update(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    before = snapshot(root)
    noop = invoke(["init", "--dry-run"], cwd=root)
    assert_ok(noop)
    assert "+++ b/" not in noop.stdout
    assert snapshot(root) == before
    write(root, "data.yml", "")  # dirty tree is fine for a dry run
    df = tmp_path / "data-change.yml"
    df.write_text("verify_cmd: make ci\n", encoding="utf-8")
    before = snapshot(root)
    changed = invoke(["init", "--dry-run", "--data-file", str(df)], cwd=root)
    assert_ok(changed)
    assert "--- a/.kuanflow/config.yaml\n+++ b/.kuanflow/config.yaml" in changed.stdout
    assert "--- a/.copier-answers.yml\n+++ b/.copier-answers.yml" in changed.stdout
    assert snapshot(root) == before
    assert not (root / ".kuanflow/cache/backup").exists()
