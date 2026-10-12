"""Contract tests C46 personal mode, C47 (Q-16, PER-01..06): `kuanflow init --personal` (TST-16)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    ALWAYS_BLOCKS,
    FIXTURES,
    NOW,
    assert_error,
    assert_ok,
    build,
    commit_all,
    describe,
    extract_body,
    git,
    git_status,
    invoke,
    read_answers,
    read_config,
    read_manifest,
    render_block,
    sha256,
    snapshot,
    write,
)

# Files the project template creates outside `.kuanflow/` and `kuan-workbench/` (use_orca false).
OTHER_CREATED = [".copier-answers.yml", "docs/adr/0000-template.md", "docs/runbooks/README.md"]


def exclude_body(prefix: str = "") -> str:
    entries = [f"/{prefix}{d}/" for d in (".kuanflow", "kuan-workbench")]
    entries += [f"/{prefix}{p}" for p in OTHER_CREATED]
    return "# Kuanflow (personal mode)\n" + "".join(f"{e}\n" for e in sorted(entries))


def exclude_file(top: Path) -> Path:
    return top / ".git" / "info" / "exclude"


def tracked_snapshot(top: Path) -> dict[str, bytes]:
    return {rel: (top / rel).read_bytes() for rel in git(top, "ls-files").splitlines()}


@pytest.mark.parametrize("name", FIXTURES)
def test_personal_init_leaves_git_status_clean(
    tmp_path: Path, env: pytest.MonkeyPatch, name: str
) -> None:
    root = build(name, tmp_path / name)
    tracked = tracked_snapshot(root)
    excl = exclude_file(root)
    excl_before = excl.read_text(encoding="utf-8") if excl.exists() else None
    result = invoke(["init", "--personal", "--yes"], cwd=root)
    assert_ok(result)
    assert "Kuanflow" in result.stdout and "installed (personal mode)" in result.stdout
    assert git_status(root, "--untracked-files=all") == "", describe(result)
    assert tracked_snapshot(root) == tracked
    assert git(root, "diff", "--name-only") == ""
    # Exclude block (hash style, bottom), entries sorted.
    text = excl.read_text(encoding="utf-8")
    body = exclude_body()
    assert extract_body(text, "hash") == body
    block = render_block(body, "hash")
    if excl_before is None:
        assert text == block
    else:
        sep = "" if excl_before.endswith("\n") or excl_before == "" else "\n"
        assert text == excl_before + sep + ("\n" if excl_before else "") + block
    # No block in tracked/agent files.
    for target in ALWAYS_BLOCKS:
        p = root / target
        if p.exists():
            assert "kuanflow:begin" not in p.read_text(encoding="utf-8"), target
            assert target in tracked, f"{target} was created in personal mode"
    # Config, answers and manifest.
    assert read_config(root)["artifacts"]["commit"] == "none"
    assert read_answers(root)["artifacts_commit"] == "none"
    data = read_manifest(root)
    assert data["mode"] == "personal"
    assert data["installed_at"] == NOW
    files = {e["path"]: e for e in data["files"]}
    entry = files["git:info/exclude"]
    assert list(entry) == ["path", "owner", "block", "sha256", "created"]
    assert entry["owner"] == "managed-block"
    assert entry["block"] == "kuanflow"
    assert entry["sha256"] == sha256(body)
    assert entry["created"] is (excl_before is None)
    assert not set(ALWAYS_BLOCKS) & set(files)


def test_personal_monorepo_root_paths_relative_to_toplevel(
    tmp_path: Path, env: pytest.MonkeyPatch
) -> None:
    top = build("monorepo", tmp_path / "monorepo")
    result = invoke(["init", "--personal", "--yes", "--root", "services/web"], cwd=top)
    assert_ok(result)
    web = top / "services/web"
    assert (web / ".kuanflow/manifest.json").is_file()
    assert not (top / ".kuanflow").exists()
    body = extract_body(exclude_file(top).read_text(encoding="utf-8"), "hash")
    assert body == exclude_body("services/web/")
    assert git_status(top, "--untracked-files=all") == ""
    assert read_config(web)["commands"]["test"] == "pnpm test"


def test_personal_from_subdir(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    result = invoke(["init", "--personal", "--yes"], cwd=root / "src/main/java")
    assert_ok(result)
    assert (root / ".kuanflow/manifest.json").is_file()
    assert git_status(root, "--untracked-files=all") == ""


def test_personal_allows_dirty_tree(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, "scratch.txt", "wip\n")
    (root / "pom.xml").write_text("<project/>\n")
    result = invoke(["init", "--personal", "--yes"], cwd=root)
    assert_ok(result)
    status = sorted(git_status(root, "--untracked-files=all").splitlines())
    assert status == [" M pom.xml", "?? scratch.txt"]
    assert (root / "pom.xml").read_text() == "<project/>\n"


def test_personal_twice_is_noop(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("gradle", tmp_path / "gradle")
    assert_ok(invoke(["init", "--personal", "--yes"], cwd=root))
    before = snapshot(root)
    result = invoke(["init", "--personal", "--yes"], cwd=root)
    assert_ok(result)
    assert "Nothing to change" in result.stdout.splitlines()
    assert snapshot(root) == before


def test_personal_tracked_answers_file_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, ".copier-answers.yml", "project_name: tracked\n")
    commit_all(root, "tracked answers")
    before = snapshot(root)
    result = invoke(["init", "--personal", "--yes"], cwd=root)
    assert_error(result, ".copier-answers.yml")
    assert snapshot(root) == before


def test_personal_force_on_tracked_path_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, ".kuanflow/README.md", "tracked notes\n")
    commit_all(root, "tracked kuanflow readme")
    before = snapshot(root)
    result = invoke(["init", "--personal", "--yes", "--force"], cwd=root)
    assert_error(result, ".kuanflow/README.md")
    assert snapshot(root) == before


def test_personal_on_project_install_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    commit_all(root, "init")
    before = snapshot(root)
    assert_error(invoke(["init", "--personal", "--yes"], cwd=root))
    assert snapshot(root) == before
