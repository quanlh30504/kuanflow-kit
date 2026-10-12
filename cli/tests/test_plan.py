"""Contract tests C41: kuanflow_cli.plan (Change, Plan, diff_text, apply)."""

from __future__ import annotations

import importlib
import os
import stat
from pathlib import Path
from types import ModuleType

import pytest

NOW = "2026-11-03T09:00:00+07:00"
STAMP = "20261103T090000"
BACKUP = ".kuanflow/cache/backup"


@pytest.fixture
def plan() -> ModuleType:
    return importlib.import_module("kuanflow_cli.plan")


@pytest.fixture
def errors() -> ModuleType:
    return importlib.import_module("kuanflow_cli.errors")


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUANFLOW_NOW", NOW)


def make_plan(mod: ModuleType, *changes: object) -> object:
    p = mod.Plan()
    for c in changes:
        p.add(c)
    return p


def write(root: Path, rel: str, data: bytes, mode: int | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    if mode is not None:
        p.chmod(mode)
    return p


def snapshot(root: Path) -> dict[str, tuple[bytes | None, int, bool]]:
    """Every entry under root (files and dirs, symlinks not followed) with bytes and mode."""
    out: dict[str, tuple[bytes | None, int, bool]] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            st = p.lstat()
            data = p.read_bytes() if stat.S_ISREG(st.st_mode) else None
            out[str(p.relative_to(root))] = (data, stat.S_IMODE(st.st_mode), p.is_symlink())
    return out


def fmode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


# --- Change / Plan ------------------------------------------------------------------------------


def test_c41_change_fields_and_defaults(plan: ModuleType) -> None:
    c = plan.Change("a/b.txt", None, b"x\n")
    assert c.path == "a/b.txt"
    assert c.before is None
    assert c.after == b"x\n"
    assert c.mode is None
    assert c.reason == ""
    c2 = plan.Change("s.sh", b"a", b"b", mode=0o755, reason="why")
    assert c2.mode == 0o755
    assert c2.reason == "why"


def test_c41_noop_change_is_dropped(plan: ModuleType) -> None:
    p = plan.Plan()
    p.add(plan.Change("same.txt", b"x\n", b"x\n"))
    p.add(plan.Change("absent.txt", None, None))
    assert len(p) == 0
    assert list(p) == []
    assert p.paths() == []


def test_c41_iteration_in_path_order(plan: ModuleType) -> None:
    p = plan.Plan()
    p.add(plan.Change("zeta.txt", None, b"z"))
    p.add(plan.Change("b/x.txt", None, b"x"))
    p.extend([plan.Change("a.txt", None, b"a"), plan.Change("b/a.txt", None, b"a")])
    expected = sorted(["zeta.txt", "b/x.txt", "a.txt", "b/a.txt"])
    assert len(p) == 4
    assert [c.path for c in p] == expected
    assert list(p.paths()) == expected


def test_c41_extend_drops_noops(plan: ModuleType) -> None:
    p = plan.Plan()
    p.extend([plan.Change("a", b"1", b"1"), plan.Change("b", b"1", b"2")])
    assert list(p.paths()) == ["b"]


# --- diff_text ----------------------------------------------------------------------------------


def test_c41_diff_empty_plan(plan: ModuleType) -> None:
    assert plan.diff_text(plan.Plan()) == ""


def test_c41_diff_modify_three_context_lines(plan: ModuleType) -> None:
    before = "".join(f"l{i}\n" for i in range(1, 11)).encode()
    after = before.replace(b"l5\n", b"L5\n")
    text = plan.diff_text(make_plan(plan, plan.Change("dir/f.txt", before, after)))
    assert text == (
        "--- a/dir/f.txt\n"
        "+++ b/dir/f.txt\n"
        "@@ -2,7 +2,7 @@\n"
        " l2\n l3\n l4\n-l5\n+L5\n l6\n l7\n l8\n"
    )


def test_c41_diff_create_uses_dev_null(plan: ModuleType) -> None:
    text = plan.diff_text(make_plan(plan, plan.Change("new.txt", None, b"a\nb\n")))
    assert text == "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1,2 @@\n+a\n+b\n"


def test_c41_diff_delete_uses_dev_null(plan: ModuleType) -> None:
    text = plan.diff_text(make_plan(plan, plan.Change("old.txt", b"a\nb\n", None)))
    assert text == "--- a/old.txt\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n"


def test_c41_diff_changes_in_path_order(plan: ModuleType) -> None:
    p = make_plan(
        plan,
        plan.Change("z.txt", None, b"z\n"),
        plan.Change("a.txt", None, b"a\n"),
        plan.Change("m.txt", b"m\n", None),
    )
    text = plan.diff_text(p)
    ia, im, iz = (text.index(h) for h in ("+++ b/a.txt", "--- a/m.txt", "+++ b/z.txt"))
    assert ia < im < iz


def test_c41_diff_decodes_invalid_utf8_with_replace(plan: ModuleType) -> None:
    text = plan.diff_text(make_plan(plan, plan.Change("bin.txt", b"ok\n", b"\xff\xfe\n")))
    assert "-ok\n" in text
    assert "+��\n" in text


def test_c41_diff_mode_change_shown_like_git(plan: ModuleType) -> None:
    # Same bytes, executable bit requested: shown as git does (contract example 100644 -> 100755).
    p = make_plan(plan, plan.Change("run.sh", b"echo\n", b"echo\n", mode=0o755))
    assert len(p) == 1
    lines = plan.diff_text(p).splitlines()
    assert "old mode 100644" in lines
    assert "new mode 100755" in lines
    assert lines.index("old mode 100644") + 1 == lines.index("new mode 100755")


# --- apply: validation --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["/etc/passwd", "../outside.txt", "a/../../x.txt", "a/../b.txt"])
def test_c41_apply_rejects_unsafe_paths_without_writing(
    plan: ModuleType, errors: ModuleType, tmp_path: Path, bad: str
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    write(root, "keep.txt", b"keep\n")
    before = snapshot(root)
    p = make_plan(plan, plan.Change("aaa.txt", None, b"ok\n"), plan.Change(bad, None, b"bad\n"))
    with pytest.raises(errors.PlanError):
        plan.apply(p, root)
    assert snapshot(root) == before
    assert not (tmp_path / "outside.txt").exists()


def test_c41_apply_rejects_symlinked_directory_component(
    plan: ModuleType, errors: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "link").symlink_to(elsewhere, target_is_directory=True)
    before = snapshot(root)
    p = make_plan(
        plan, plan.Change("aaa.txt", None, b"ok\n"), plan.Change("link/f.txt", None, b"x")
    )
    with pytest.raises(errors.PlanError):
        plan.apply(p, root)
    assert snapshot(root) == before
    assert list(elsewhere.iterdir()) == []


def test_c41_apply_rejects_symlink_target_file(
    plan: ModuleType, errors: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    real = tmp_path / "real.txt"
    real.write_bytes(b"real\n")
    (root / "l.txt").symlink_to(real)
    before = snapshot(root)
    p = make_plan(plan, plan.Change("l.txt", b"real\n", b"changed\n"))
    with pytest.raises(errors.PlanError):
        plan.apply(p, root)
    assert snapshot(root) == before
    assert real.read_bytes() == b"real\n"


def test_c41_apply_rejects_delete_of_symlink(
    plan: ModuleType, errors: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    real = tmp_path / "real.txt"
    real.write_bytes(b"real\n")
    (root / "l.txt").symlink_to(real)
    with pytest.raises(errors.PlanError):
        plan.apply(make_plan(plan, plan.Change("l.txt", b"real\n", None)), root)
    assert (root / "l.txt").is_symlink()


@pytest.mark.parametrize(
    ("disk", "before"),
    [(b"disk\n", b"old\n"), (b"disk\n", None), (None, b"old\n")],
    ids=["bytes-differ", "exists-but-before-none", "missing-but-before-bytes"],
)
def test_c41_apply_stale_before_is_conflict_nothing_written(
    plan: ModuleType,
    errors: ModuleType,
    tmp_path: Path,
    disk: bytes | None,
    before: bytes | None,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    write(root, "other.txt", b"other\n")
    if disk is not None:
        write(root, "zz/stale.txt", disk)
    snap = snapshot(root)
    p = make_plan(
        plan,
        plan.Change("aaa-new.txt", None, b"new\n"),
        plan.Change("other.txt", b"other\n", b"changed\n"),
        plan.Change("zz/stale.txt", before, b"after\n"),
    )
    with pytest.raises(errors.PlanConflictError) as exc:
        plan.apply(p, root)
    assert isinstance(exc.value, errors.PlanError)
    assert "zz/stale.txt" in str(exc.value)
    assert snapshot(root) == snap


# --- apply: backups -----------------------------------------------------------------------------


def test_c41_apply_backs_up_modified_and_deleted(plan: ModuleType, tmp_path: Path) -> None:
    root = tmp_path
    write(root, "mod.txt", b"old mod\n")
    write(root, "d/del.txt", b"old del\n")
    p = make_plan(
        plan,
        plan.Change("mod.txt", b"old mod\n", b"new mod\n"),
        plan.Change("d/del.txt", b"old del\n", None),
        plan.Change("created.txt", None, b"fresh\n"),
    )
    result = plan.apply(p, root)
    expected = root / BACKUP / STAMP
    assert result is not None
    assert Path(result) == expected
    assert (expected / "mod.txt").read_bytes() == b"old mod\n"
    assert (expected / "d/del.txt").read_bytes() == b"old del\n"
    assert not (expected / "created.txt").exists()
    backed = sorted(str(q.relative_to(expected)) for q in expected.rglob("*") if q.is_file())
    assert backed == ["d/del.txt", "mod.txt"]
    assert (root / "mod.txt").read_bytes() == b"new mod\n"
    assert not (root / "d/del.txt").exists()
    assert (root / "created.txt").read_bytes() == b"fresh\n"


def test_c41_apply_creates_only_returns_none(plan: ModuleType, tmp_path: Path) -> None:
    result = plan.apply(make_plan(plan, plan.Change("a/new.txt", None, b"x")), tmp_path)
    assert result is None
    assert not (tmp_path / BACKUP).exists()


def test_c41_apply_backup_false(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "f.txt", b"old")
    result = plan.apply(
        make_plan(plan, plan.Change("f.txt", b"old", b"new")), tmp_path, backup=False
    )
    assert result is None
    assert not (tmp_path / BACKUP).exists()
    assert (tmp_path / "f.txt").read_bytes() == b"new"


def test_c41_apply_backup_dir_suffix_when_stamp_taken(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "f.txt", b"v1")
    first = plan.apply(make_plan(plan, plan.Change("f.txt", b"v1", b"v2")), tmp_path)
    second = plan.apply(make_plan(plan, plan.Change("f.txt", b"v2", b"v3")), tmp_path)
    assert first is not None and second is not None
    first, second = Path(first), Path(second)
    assert first == tmp_path / BACKUP / STAMP
    assert second != first
    assert second.parent == tmp_path / BACKUP
    assert second.name.startswith(STAMP + "-")
    assert second.name[len(STAMP) + 1 :].isdigit()
    assert (first / "f.txt").read_bytes() == b"v1"
    assert (second / "f.txt").read_bytes() == b"v2"


def test_c41_apply_returns_none_for_empty_plan(plan: ModuleType, tmp_path: Path) -> None:
    assert plan.apply(plan.Plan(), tmp_path) is None
    assert list(tmp_path.iterdir()) == []


# --- apply: writes ------------------------------------------------------------------------------


def test_c41_apply_creates_parent_dirs(plan: ModuleType, tmp_path: Path) -> None:
    plan.apply(make_plan(plan, plan.Change("a/b/c/new.txt", None, b"deep\n")), tmp_path)
    assert (tmp_path / "a/b/c/new.txt").read_bytes() == b"deep\n"


def test_c41_apply_is_atomic_via_os_replace(
    plan: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, "sub/f.txt", b"old\n")
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def spy(src: object, dst: object, *args: object, **kwargs: object) -> None:
        calls.append((Path(os.fsdecode(src)), Path(os.fsdecode(dst))))  # type: ignore[arg-type]
        real_replace(src, dst, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", spy)
    p = make_plan(
        plan,
        plan.Change("sub/f.txt", b"old\n", b"new\n"),
        plan.Change("sub/g.txt", None, b"g\n"),
    )
    plan.apply(p, tmp_path, backup=False)
    targets = {dst.resolve(): src for src, dst in calls}
    for rel in ("sub/f.txt", "sub/g.txt"):
        dst = (tmp_path / rel).resolve()
        assert dst in targets, f"{rel} not written via os.replace"
        assert targets[dst].parent.resolve() == dst.parent
    assert sorted(q.name for q in (tmp_path / "sub").iterdir()) == ["f.txt", "g.txt"]


def test_c41_apply_leaves_no_temp_files(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "a.txt", b"1")
    write(tmp_path, "d/b.txt", b"2")
    p = make_plan(
        plan,
        plan.Change("a.txt", b"1", b"one"),
        plan.Change("d/b.txt", b"2", b"two"),
        plan.Change("d/c.txt", None, b"three"),
    )
    plan.apply(p, tmp_path, backup=False)
    files = sorted(str(q.relative_to(tmp_path)) for q in tmp_path.rglob("*") if q.is_file())
    assert files == ["a.txt", "d/b.txt", "d/c.txt"]


def test_c41_apply_new_file_default_mode_644(
    plan: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = os.umask(0o077)
    try:
        plan.apply(make_plan(plan, plan.Change("n.txt", None, b"x")), tmp_path)
    finally:
        os.umask(old)
    assert fmode(tmp_path / "n.txt") == 0o644


def test_c41_apply_new_file_mode_755(plan: ModuleType, tmp_path: Path) -> None:
    plan.apply(
        make_plan(plan, plan.Change("bin/run.sh", None, b"#!/bin/sh\n", mode=0o755)), tmp_path
    )
    assert fmode(tmp_path / "bin/run.sh") == 0o755


def test_c41_apply_existing_mode_kept_when_none(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "secret.txt", b"a", mode=0o600)
    write(tmp_path, "tool.sh", b"a", mode=0o755)
    p = make_plan(
        plan,
        plan.Change("secret.txt", b"a", b"b"),
        plan.Change("tool.sh", b"a", b"b"),
    )
    plan.apply(p, tmp_path, backup=False)
    assert fmode(tmp_path / "secret.txt") == 0o600
    assert fmode(tmp_path / "tool.sh") == 0o755


def test_c41_apply_existing_mode_changed_when_given(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "a.sh", b"a", mode=0o644)
    write(tmp_path, "b.sh", b"b", mode=0o755)
    p = make_plan(
        plan,
        plan.Change("a.sh", b"a", b"a2", mode=0o755),
        plan.Change("b.sh", b"b", b"b2", mode=0o644),
    )
    plan.apply(p, tmp_path, backup=False)
    assert fmode(tmp_path / "a.sh") == 0o755
    assert fmode(tmp_path / "b.sh") == 0o644


def test_c41_apply_delete_removes_empty_parents(plan: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "root"
    write(root, "a/b/c/only.txt", b"x")
    write(root, "a/keep.txt", b"k")
    plan.apply(make_plan(plan, plan.Change("a/b/c/only.txt", b"x", None)), root, backup=False)
    assert not (root / "a/b").exists()
    assert (root / "a").is_dir()
    assert (root / "a/keep.txt").read_bytes() == b"k"


def test_c41_apply_delete_never_removes_root(plan: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "root"
    write(root, "sub/x.txt", b"x")
    write(root, "top.txt", b"t")
    p = make_plan(plan, plan.Change("sub/x.txt", b"x", None), plan.Change("top.txt", b"t", None))
    plan.apply(p, root, backup=False)
    assert root.is_dir()
    assert list(root.iterdir()) == []


def test_c41_apply_delete_keeps_nonempty_parent(plan: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "d/a.txt", b"a")
    write(tmp_path, "d/b.txt", b"b")
    plan.apply(make_plan(plan, plan.Change("d/a.txt", b"a", None)), tmp_path, backup=False)
    assert sorted(q.name for q in (tmp_path / "d").iterdir()) == ["b.txt"]
