"""Project root resolution (C37): git top level plus nearest ``.kuanflow/manifest.json``."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from kuanflow_cli.errors import RootError

MANIFEST = Path(".kuanflow/manifest.json")


def _git_env() -> dict[str, str]:
    # C36d: drop inherited GIT_* (e.g. GIT_DIR from a hook) so git looks at the given directory.
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git_toplevel(path: Path) -> Path | None:
    """Resolved git work-tree top level containing ``path``; ``None`` outside a work tree."""
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.rstrip("\n")).resolve()


def find_root(start: Path, explicit: Path | None = None) -> Path:
    """``explicit`` if given, else the nearest manifest dir from ``start`` up to the top level."""
    if explicit is not None:
        root = explicit.resolve()
        if not root.is_dir():
            raise RootError(f"root is not a directory: {root}")
        if git_toplevel(root) is None:
            raise RootError(f"root is not inside a git repository: {root}")
        return root

    top = git_toplevel(start)
    if top is None:
        raise RootError("not inside a git repository")
    # Walk up from start to the top level inclusive, never above it.
    here = start.resolve()
    chain = [here, *here.parents]
    chain = chain[: chain.index(top) + 1] if top in chain else []
    for directory in chain:
        if (directory / MANIFEST).is_file():
            return directory
    return top
