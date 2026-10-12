"""Contract tests C47 step 5/7, C40 (Q-22): `kuanflow init` twice is a no-op (PKG §12.5, TST-11)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    FIXTURES,
    LATER,
    NOW,
    assert_ok,
    build,
    commit_all,
    doctor_summary,
    git_status,
    invoke,
    read_answers,
    read_config,
    read_manifest,
    sha256,
    snapshot,
)


@pytest.mark.parametrize("name", FIXTURES)
def test_init_twice_changes_nothing(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    root = build(name, tmp_path / name)
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "kuanflow init")
    before = snapshot(root)
    manifest_before = (root / ".kuanflow/manifest.json").read_bytes()
    env.setenv("KUANFLOW_NOW", LATER)
    result = invoke(["init", "--yes"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert "Nothing to change" in lines
    assert not [ln for ln in lines if ln.startswith(("create ", "update ", "delete "))]
    assert doctor_summary(result.stdout)[2] == 0
    after = snapshot(root)
    assert after == before
    assert (root / ".kuanflow/manifest.json").read_bytes() == manifest_before
    data = read_manifest(root)
    assert data["installed_at"] == NOW
    assert "updated_at" not in data
    assert git_status(root, "--untracked-files=all") == ""


def test_reinit_with_changed_answer_updates(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "kuanflow init")
    claude_before = (root / "CLAUDE.md").read_bytes()
    df = tmp_path / "change.yml"
    df.write_text("verify_cmd: make ci\n", encoding="utf-8")
    env.setenv("KUANFLOW_NOW", LATER)
    result = invoke(["init", "--yes", "--data-file", str(df)], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert "update .kuanflow/config.yaml" in lines
    assert "update .copier-answers.yml" in lines
    assert "update CLAUDE.md" not in lines
    assert read_config(root)["commands"]["verify"] == "make ci"
    assert read_answers(root)["verify_cmd"] == "make ci"
    assert (root / "CLAUDE.md").read_bytes() == claude_before
    data = read_manifest(root)
    assert data["installed_at"] == NOW
    assert data["updated_at"] == LATER
    assert list(data)[:5] == [
        "manifest_version",
        "kuanflow_version",
        "template",
        "installed_at",
        "updated_at",
    ]
    files = {e["path"]: e for e in data["files"]}
    config = (root / ".kuanflow/config.yaml").read_bytes()
    assert files[".kuanflow/config.yaml"]["sha256"] == sha256(config)
    # The answer persists: a plain re-run keeps it and changes nothing.
    commit_all(root, "answers")
    before = snapshot(root)
    again = invoke(["init", "--yes"], cwd=root)
    assert_ok(again)
    assert "Nothing to change" in again.stdout.splitlines()
    assert snapshot(root) == before


def test_reinit_answer_changes_block_body(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "kuanflow init")
    df = tmp_path / "change.yml"
    df.write_text("artifacts_commit: full\n", encoding="utf-8")
    result = invoke(["init", "--yes", "--data-file", str(df)], cwd=root)
    assert_ok(result)
    assert "update .gitignore" in result.stdout.splitlines()
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "kuan-workbench/work/*/research.md" not in gitignore
    assert "artifacts.commit = full" in gitignore
