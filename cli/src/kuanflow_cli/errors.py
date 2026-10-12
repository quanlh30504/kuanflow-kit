"""CLI error types (contract C36a). Commands print ``error: <message>`` and exit ``exit_code``."""

from __future__ import annotations


class KuanflowError(Exception):
    """Base for every expected CLI error."""

    exit_code = 1


class RootError(KuanflowError):
    """No usable project root (not a git work tree, bad ``--root``)."""


class DirtyTreeError(KuanflowError):
    """The working tree has uncommitted or untracked changes."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = list(paths)
        shown = "\n  ".join(self.paths[:20])
        more = f"\n  … and {len(self.paths) - 20} more" if len(self.paths) > 20 else ""
        super().__init__(f"working tree is not clean; commit or stash first:\n  {shown}{more}")


class AnswersError(KuanflowError):
    """Invalid answers (``--data-file``)."""


class ManifestError(KuanflowError):
    """``.kuanflow/manifest.json`` is invalid."""


class PlanError(KuanflowError):
    """A change plan cannot be applied safely."""


class PlanConflictError(PlanError):
    """A file changed on disk after the plan was made."""


class BlockError(KuanflowError):
    """Managed-block markers are broken."""


class KeysError(KuanflowError):
    """A JSON/TOML file cannot be key-merged."""


class RenderError(KuanflowError):
    """Copier/Jinja rendering failed."""


class NotInstalledError(KuanflowError):
    """Kuanflow is not installed in this project (no manifest)."""
