"""Contract tests C50: `kuanflow uninstall` (CMD-21, PKG §12.5, TST-15)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    FIXTURES,
    PROJECT_LOCAL_OWNED,
    assert_error,
    assert_ok,
    build,
    commit_all,
    describe,
    files_under,
    git_status,
    invoke,
    snapshot,
    write,
)

# Local-owned files the project template creates (use_orca false): kept by uninstall.
LEFTOVERS = PROJECT_LOCAL_OWNED - {"orca.yaml"}


def file_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        k: (v, m)
        for k, (v, m) in snapshot(root).items()
        if v is not None and not k.startswith("git:")
    }


@pytest.mark.parametrize("name", FIXTURES)
def test_uninstall_restores_fixture(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    root = build(name, tmp_path / name)
    before = file_snapshot(root)
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "kuanflow init")
    leftovers = {rel: (root / rel).read_bytes() for rel in LEFTOVERS}
    result = invoke(["uninstall"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert lines[-1] == "Kuanflow removed"
    # Pre-existing files byte-identical (bytes and mode).
    after = file_snapshot(root)
    for rel, data in before.items():
        assert after.get(rel) == data, rel
    # Only pre-existing files and local-owned leftovers remain; nothing under .kuanflow/cache.
    assert files_under(root, skip_cache=False) == set(before) | LEFTOVERS
    for rel, data in leftovers.items():
        assert (root / rel).read_bytes() == data, rel
    assert (root / "docs").is_dir() and (root / "kuan-workbench").is_dir()
    kuanflow_files = {p for p in files_under(root, skip_cache=False) if p.startswith(".kuanflow/")}
    assert kuanflow_files == {".kuanflow/templates/.gitkeep"}
    assert not (root / ".kuanflow/manifest.json").exists()
    assert not (root / ".kuanflow/cache").exists()
    assert not (root / ".kuanflow/scripts").exists()  # emptied directories are removed
    if ".github/pull_request_template.md" not in before:
        assert not (root / ".github").exists()
    assert "delete .kuanflow/README.md" in lines
    assert "delete .copier-answers.yml" in lines


def test_uninstall_removes_blocks_from_preexisting(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    claude = (root / "CLAUDE.md").read_bytes()
    gitignore = (root / ".gitignore").read_bytes()
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "kuanflow init")
    result = invoke(["uninstall"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert "remove-block CLAUDE.md" in lines
    assert "remove-block .gitignore" in lines
    assert (root / "CLAUDE.md").read_bytes() == claude
    assert (root / ".gitignore").read_bytes() == gitignore
    assert not (root / "AGENTS.md").exists()  # created, block only -> deleted


def test_uninstall_keeps_modified_file(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    write(root, ".kuanflow/README.md", "edited by the team\n")
    commit_all(root, "init + edit")
    result = invoke(["uninstall"], cwd=root)
    assert_ok(result)
    assert "keep .kuanflow/README.md (modified; use --force)" in result.stdout.splitlines()
    assert (root / ".kuanflow/README.md").read_text() == "edited by the team\n"
    assert not (root / ".kuanflow/manifest.json").exists()


def test_uninstall_force_deletes_modified(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    write(root, ".kuanflow/README.md", "edited by the team\n")
    commit_all(root, "init + edit")
    result = invoke(["uninstall", "--force"], cwd=root)
    assert_ok(result)
    assert "delete .kuanflow/README.md" in result.stdout.splitlines()
    assert not (root / ".kuanflow/README.md").exists()
    assert not (root / ".kuanflow/cache/backup").exists()  # no backups (D-P4-3)


def test_uninstall_speckit_agents_md_restored(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("speckit", tmp_path / "speckit")
    original = (root / "AGENTS.md").read_bytes()
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    assert_ok(invoke(["uninstall"], cwd=root))
    assert (root / "AGENTS.md").read_bytes() == original


def test_uninstall_dry_run(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    before = snapshot(root)
    result = invoke(["uninstall", "--dry-run"], cwd=root)
    assert_ok(result)
    assert snapshot(root) == before
    out = result.stdout
    assert "--- a/.kuanflow/README.md\n+++ /dev/null" in out
    assert "--- a/CLAUDE.md\n+++ b/CLAUDE.md" in out


def test_uninstall_not_installed(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    before = snapshot(root)
    assert_error(invoke(["uninstall"], cwd=root))
    assert snapshot(root) == before


def test_uninstall_dirty_tree_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    write(root, "wip.txt", "wip\n")
    before = snapshot(root)
    assert_error(invoke(["uninstall"], cwd=root), "wip.txt")
    assert snapshot(root) == before


@pytest.mark.parametrize("name", FIXTURES)
def test_uninstall_personal(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    root = build(name, tmp_path / name)
    write(root, "wip.txt", "wip\n")  # personal mode: dirty tree allowed
    exclude = root / ".git/info/exclude"
    exclude_before = exclude.read_bytes() if exclude.exists() else None
    status_before = git_status(root)
    status_all_before = git_status(root, "--untracked-files=all")
    files_before = file_snapshot(root)
    assert_ok(invoke(["init", "--personal", "--yes"], cwd=root))
    result = invoke(["uninstall"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert lines[-1] == "Kuanflow removed"
    assert "remove-block git:info/exclude" in lines
    if exclude_before is None:
        assert not exclude.exists() or exclude.read_bytes() == b""
    else:
        assert exclude.read_bytes() == exclude_before
    # C50a: unmodified local-owned files are deleted too -> git status exactly as before init.
    assert git_status(root) == status_before, describe(result)
    assert git_status(root, "--untracked-files=all") == status_all_before
    assert file_snapshot(root) == files_before
    assert not (root / ".kuanflow").exists()
    assert not (root / "docs").exists()
    assert not (root / "kuan-workbench").exists()
    assert "delete docs/runbooks/README.md" in lines


def test_uninstall_personal_keeps_modified_local_owned(
    tmp_path: Path, env: pytest.MonkeyPatch
) -> None:
    root = build("maven", tmp_path / "maven")
    files_before = file_snapshot(root)
    assert_ok(invoke(["init", "--personal", "--yes"], cwd=root))
    write(root, "docs/runbooks/README.md", "# Runbooks\n\nOur own index.\n")
    result = invoke(["uninstall"], cwd=root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert "keep docs/runbooks/README.md (modified)" in lines
    assert (root / "docs/runbooks/README.md").read_text() == "# Runbooks\n\nOur own index.\n"
    assert "delete docs/adr/0000-template.md" in lines
    after = file_snapshot(root)
    assert set(after) == set(files_before) | {"docs/runbooks/README.md"}
    for rel, data in files_before.items():
        assert after[rel] == data, rel
    untracked = {
        ln[3:] for ln in git_status(root, "--untracked-files=all").splitlines() if ln[:3] == "?? "
    }
    assert untracked == {"docs/runbooks/README.md"}, describe(result)


def test_uninstall_project_mode_keeps_local_owned(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    """C50a applies to personal mode only: project mode keeps unmodified local-owned files."""
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    assert_ok(invoke(["uninstall"], cwd=root))
    for rel in LEFTOVERS:
        assert (root / rel).is_file(), rel
