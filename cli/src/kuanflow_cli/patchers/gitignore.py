"""``.gitignore`` / ``info/exclude`` patching (contract C43): a hash-style block at the bottom."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from kuanflow_cli.errors import RootError
from kuanflow_cli.patchers import managed_block


def _git_env() -> dict[str, str]:
    # Inherited GIT_* (e.g. GIT_DIR from a hook) would point git at another repository (C36d).
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def exclude_path(root: Path | str) -> Path:
    """``info/exclude`` as git resolves it from ``root`` (linked worktrees share the common dir)."""
    root = Path(root)
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "info/exclude"],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if proc.returncode != 0:
        raise RootError(f"not a git repository: {root} ({proc.stderr.strip()})")
    # git prints the path relative to the directory given with -C (or absolute).
    return root / proc.stdout.rstrip("\n")


def upsert(text: str | None, body: str) -> str:
    """``managed_block.upsert`` with ``style="hash"``, ``position="bottom"``."""
    return managed_block.upsert(text, body, "hash", "bottom")


def remove(text: str) -> str:
    """``managed_block.remove`` with ``style="hash"``."""
    return managed_block.remove(text, "hash")
