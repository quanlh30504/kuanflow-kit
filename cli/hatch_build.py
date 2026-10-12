"""Hatch hooks for kuanflow-cli.

* Metadata hook: version = repo-root ``VERSION`` (SemVer) converted to PEP 440.
* Build hook: bundles ``plugins/kuanflow`` and ``templates`` into the wheel under
  ``kuanflow_cli/_content/`` and copies VERSION + content into the sdist so a wheel
  built from the sdist is identical.

Source-root lookup: ``<cli>`` itself when it holds ``VERSION`` (unpacked sdist, where the build
hook placed the files), else ``<cli>/..`` (repo checkout, git URL with ``#subdirectory=cli``).
The SemVer -> PEP 440 mapping lives in ``semver_pep440.py`` next to this file (contract C9).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.metadata.plugin.interface import MetadataHookInterface


def _load_semver() -> ModuleType:
    # Loaded by path: hatchling imports this file as a script, so the sibling is not on sys.path.
    path = Path(__file__).with_name("semver_pep440.py")
    spec = importlib.util.spec_from_file_location("_kuanflow_semver_pep440", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semver_pep440 = _load_semver()

# (source relative to the source root, destination inside the wheel)
_WHEEL_CONTENT = [
    ("plugins/kuanflow", "kuanflow_cli/_content/plugins/kuanflow"),
    ("templates", "kuanflow_cli/_content/templates"),
]


def source_root(project_root: str | Path) -> Path:
    cli = Path(project_root)
    for candidate in (cli, cli.parent):
        if (candidate / "VERSION").is_file():
            return candidate
    raise FileNotFoundError(f"VERSION not found in {cli} or {cli.parent}")


def read_version(root: str | Path) -> str:
    """PEP 440 version from the ``VERSION`` file found via ``source_root(root)``."""
    raw = (source_root(root) / "VERSION").read_text(encoding="utf-8").strip()
    return semver_pep440.to_pep440(raw)


class VersionMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict[str, Any]) -> None:
        metadata["version"] = read_version(self.root)


class ContentBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = source_root(self.root)
        if self.target_name == "sdist":
            if root != Path(self.root):  # building from the repo: copy shared files in
                build_data["force_include"][str(root / "VERSION")] = "VERSION"
                for src, _ in _WHEEL_CONTENT:
                    build_data["force_include"][str(root / src)] = src
            return
        if self.target_name == "wheel" and version == "editable":
            return  # editable installs read content from the repo checkout
        for src, dest in _WHEEL_CONTENT:
            build_data["force_include"][str(root / src)] = dest
