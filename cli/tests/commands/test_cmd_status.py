"""Contract tests C48: `kuanflow status` (CMD-18)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    assert_error,
    assert_ok,
    build,
    commit_all,
    current_version,
    edit_block_body,
    invoke,
    read_manifest,
    write,
    write_manifest,
)

ALL_MATCH = "All managed files match the manifest."


def installed(tmp_path: Path, name: str = "empty", *extra: str) -> Path:
    root = build(name, tmp_path / name)
    assert_ok(invoke(["init", "--yes", *extra], cwd=root))
    commit_all(root, "kuanflow init")
    return root


def test_status_not_installed(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    assert_error(invoke(["status"], cwd=root))


def test_status_outside_git(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert_error(invoke(["status"], cwd=plain))


def test_status_clean(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    version = current_version()
    assert result.stdout.splitlines() == [
        f"Kuanflow {version} (project mode, template project)",
        f"CLI {version}",
        "Agents: none",
        ALL_MATCH,
    ]


def test_status_reports_problems_in_path_order(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    write(root, ".kuanflow/README.md", "edited\n")
    (root / ".kuanflow/scripts/guard-bash.sh").unlink()
    (root / "docs/runbooks/README.md").unlink()  # local-owned: never reported
    write(root, "kuan-workbench/wiki/.gitkeep", "edited local-owned\n")  # local-owned
    edit_block_body(root / "AGENTS.md", "html", "- my rule\n")
    (root / "CLAUDE.md").unlink()
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    write(root, ".gitignore", gi.replace("# kuanflow:end\n", ""))
    write(root, ".github/pull_request_template.md", "# PR\n")  # file present, no block
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert lines[3:] == [
        "block-missing .github/pull_request_template.md",
        "block-broken .gitignore",
        "modified .kuanflow/README.md",
        "missing .kuanflow/scripts/guard-bash.sh",
        "block-edited AGENTS.md",
        "block-missing CLAUDE.md",
    ]
    assert ALL_MATCH not in result.stdout


def test_status_modified_merge_required(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    cfg = root / ".kuanflow/config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n# local note\n", encoding="utf-8")
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    assert result.stdout.splitlines()[3:] == ["modified .kuanflow/config.yaml"]


def test_status_uses_manifest_version(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    data = read_manifest(root)
    data["kuanflow_version"] = "0.0.1"
    data["agents"] = ["claude", "codex"]
    write_manifest(root, data)
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert lines[0] == "Kuanflow 0.0.1 (project mode, template project)"
    assert lines[1] == f"CLI {current_version()}"
    assert lines[2] == "Agents: claude, codex"


def test_status_personal_mode(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    assert_ok(invoke(["init", "--personal", "--yes"], cwd=root))
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert lines[0] == f"Kuanflow {current_version()} (personal mode, template project)"
    assert lines[-1] == ALL_MATCH
    exclude = root / ".git/info/exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8").replace("/kuan-workbench/\n", ""), encoding="utf-8"
    )
    edited = invoke(["status"], cwd=root)
    assert_ok(edited)
    assert edited.stdout.splitlines()[3:] == ["block-edited git:info/exclude"]


def test_status_knowledge_repo(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "knowledge")
    assert_ok(invoke(["init", "--yes", "--template", "knowledge-repo"], cwd=root))
    result = invoke(["status"], cwd=root)
    assert_ok(result)
    assert result.stdout.splitlines()[0] == (
        f"Kuanflow {current_version()} (project mode, template knowledge-repo)"
    )
    assert result.stdout.splitlines()[-1] == ALL_MATCH


def test_status_root_option_and_subdir(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path, "maven")
    deep = root / "src/main/java/com/example"
    assert_ok(invoke(["status"], cwd=deep))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = invoke(["status", "--root", str(root)], cwd=elsewhere)
    assert_ok(result)
    assert result.stdout.splitlines()[-1] == ALL_MATCH


def test_status_invalid_manifest(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    (root / ".kuanflow/manifest.json").write_text("{not json\n", encoding="utf-8")
    assert_error(invoke(["status"], cwd=root))
