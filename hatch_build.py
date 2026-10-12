"""Hatch metadata hook for kuanflow-cli: version = ``VERSION`` (SemVer) converted to PEP 440.

Content bundling is declarative (``force-include`` in ``pyproject.toml``); this file only sets the
version. The mapping lives in ``cli/src/kuanflow_cli/semver.py`` (contract C9r), loaded by path
because hatchling runs this file as a script and the package itself needs typer to import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from hatchling.metadata.plugin.interface import MetadataHookInterface


def _load_semver() -> ModuleType:
    path = Path(__file__).parent / "cli" / "src" / "kuanflow_cli" / "semver.py"
    spec = importlib.util.spec_from_file_location("_kuanflow_build_semver", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semver = _load_semver()


def read_version(root: str | Path) -> str:
    """PEP 440 version from ``<root>/VERSION``; a VERSION outside the project root is never used."""
    raw = (Path(root) / "VERSION").read_text(encoding="utf-8").strip()
    return semver.to_pep440(raw)


class VersionMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict[str, Any]) -> None:
        metadata["version"] = read_version(self.root)
