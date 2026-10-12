"""Change plans (contract C41): every file write the CLI makes goes through ``apply``.

A plan is a set of whole-file changes keyed by root-relative posix path. ``apply`` validates
the whole plan against the disk before the first write, backs up what it will overwrite or
delete, and writes each file atomically. Symlinks are never followed.
"""

from __future__ import annotations

import difflib
import os
import stat
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from kuanflow_cli import clock
from kuanflow_cli.errors import PlanConflictError, PlanError

BACKUP_DIR = ".kuanflow/cache/backup"

_DEFAULT_MODE = 0o644


@dataclass(frozen=True)
class Change:
    """A whole-file change; ``before``/``after``: bytes or ``None`` (absent; after=None deletes).

    ``mode`` is ``0o755``/``0o644`` or ``None`` (new file -> ``0o644``, existing -> keep).
    """

    path: str
    before: bytes | None
    after: bytes | None
    mode: int | None = None
    reason: str = ""

    def is_noop(self) -> bool:
        """Same bytes and no mode to apply."""
        return self.before == self.after and (self.mode is None or self.after is None)


class Plan:
    """Changes keyed by path, iterated in path order; no-op changes are dropped."""

    def __init__(self) -> None:
        self._changes: dict[str, Change] = {}

    def add(self, change: Change) -> None:
        """Add ``change`` unless it is a no-op; a second change for the same path is an error."""
        if change.is_noop():
            return
        if change.path in self._changes:
            raise PlanError(f"two changes for {change.path}")
        self._changes[change.path] = change

    def extend(self, changes: Iterable[Change]) -> None:
        """``add`` each change."""
        for change in changes:
            self.add(change)

    def paths(self) -> list[str]:
        """Changed paths in order."""
        return sorted(self._changes)

    def __iter__(self) -> Iterator[Change]:
        return (self._changes[p] for p in self.paths())

    def __len__(self) -> int:
        return len(self._changes)


# --- diff ---------------------------------------------------------------------------------------


def _lines(data: bytes | None) -> list[str]:
    # Split on "\n" only, keeping it, so "\r" and other separators stay inside their line.
    if not data:
        return []
    parts = data.decode("utf-8", errors="replace").split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    return lines + [parts[-1]] if parts[-1] else lines


def _diff_one(change: Change) -> str:
    out = []
    # A same-bytes change is kept only for its mode, so the old mode is the other one.
    if change.before is not None and change.before == change.after and change.mode is not None:
        old = 0o755 if change.mode == 0o644 else 0o644
        out += [f"old mode 100{old:o}\n", f"new mode 100{change.mode:o}\n"]
        out += [f"--- a/{change.path}\n", f"+++ b/{change.path}\n"]
        return "".join(out)
    fromfile = "/dev/null" if change.before is None else f"a/{change.path}"
    tofile = "/dev/null" if change.after is None else f"b/{change.path}"
    for line in difflib.unified_diff(
        _lines(change.before), _lines(change.after), fromfile, tofile, n=3
    ):
        out.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return "".join(out)


def diff_text(plan: Plan) -> str:
    """Unified diff of every change in path order (``""`` for an empty plan)."""
    return "".join(_diff_one(change) for change in plan)


# --- apply --------------------------------------------------------------------------------------


def _parts(path: str) -> tuple[str, ...]:
    pure = PurePosixPath(path)
    if not path or pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise PlanError(f"unsafe path in plan: {path!r}")
    return pure.parts


def _check_dirs(root: Path, parts: tuple[str, ...], shown: str) -> None:
    # Every existing parent component must be a real directory, never a symlink.
    current = root
    for part in parts:
        current = current / part
        try:
            st = current.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(st.st_mode):
            raise PlanError(f"refusing to write through symlink {current} ({shown})")
        if not stat.S_ISDIR(st.st_mode):
            raise PlanError(f"{current} is not a directory ({shown})")


def _disk_bytes(target: Path, shown: str) -> bytes | None:
    try:
        st = target.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(st.st_mode):
        raise PlanError(f"refusing to change symlink {shown}")
    if not stat.S_ISREG(st.st_mode):
        raise PlanError(f"{shown} is not a regular file")
    return target.read_bytes()


def _validate(plan: Plan, root: Path) -> None:
    creating = {c.path for c in plan if c.after is not None}
    for change in plan:
        parts = _parts(change.path)
        for i in range(1, len(parts)):
            if "/".join(parts[:i]) in creating:
                raise PlanError(f"{change.path} is inside {'/'.join(parts[:i])}, also a file")
        _check_dirs(root, parts[:-1], change.path)
        if _disk_bytes(root / change.path, change.path) != change.before:
            raise PlanConflictError(f"{change.path} changed on disk since the plan was made")


def _backup_dir(root: Path) -> Path:
    base = root / BACKUP_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = clock.stamp()
    n = 0
    while True:
        candidate = base / (stamp if n == 0 else f"{stamp}-{n}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            n += 1


def _write_atomic(target: Path, data: bytes, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            os.fchmod(fh.fileno(), mode)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _delete(root: Path, target: Path) -> None:
    target.unlink()
    parent = target.parent
    while parent != root and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def apply(plan: Plan, root: Path | str, *, backup: bool = True) -> Path | None:
    """Validate, back up, then write ``plan`` under ``root``; returns the backup dir or ``None``.

    Raises ``PlanError`` (unsafe path, symlink) or ``PlanConflictError`` (stale ``before``)
    before anything is written.
    """
    root = Path(root)
    _validate(plan, root)
    existing = [c for c in plan if c.before is not None]
    backup_dir: Path | None = None
    if backup and existing:
        _check_dirs(root, PurePosixPath(BACKUP_DIR).parts, BACKUP_DIR)
        backup_dir = _backup_dir(root)
        for change in existing:
            copy = backup_dir / change.path
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(change.before)  # validated equal to the disk bytes

    for change in plan:
        target = root / change.path
        if change.after is None:
            _delete(root, target)
            continue
        mode = change.mode
        if mode is None:
            existed = change.before is not None
            mode = stat.S_IMODE(target.lstat().st_mode) if existed else _DEFAULT_MODE
        _write_atomic(target, change.after, mode)
    return backup_dir
