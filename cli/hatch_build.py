"""Hatch hooks for kuanflow-cli.

* Metadata hook: version = repo-root ``VERSION`` (SemVer) converted to PEP 440.
* Build hook: bundles ``plugins/kuanflow`` and ``templates`` into the wheel under
  ``kuanflow_cli/_content/`` and copies VERSION + content into the sdist so a wheel
  built from the sdist is identical.

Source-root lookup: ``<cli>/..`` (repo checkout, git URL with ``#subdirectory=cli``)
or ``<cli>`` itself (unpacked sdist, where the build hook placed the files).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.metadata.plugin.interface import MetadataHookInterface

_SEMVER = re.compile(r"(\d+\.\d+\.\d+)(?:-(dev|alpha\.(\d+)|beta\.(\d+)|rc\.(\d+)))?")

# (source relative to the source root, destination inside the wheel)
_WHEEL_CONTENT = [
    ("plugins/kuanflow", "kuanflow_cli/_content/plugins/kuanflow"),
    ("templates", "kuanflow_cli/_content/templates"),
]


def semver_to_pep440(version: str) -> str:
    m = _SEMVER.fullmatch(version)
    if m is None:
        raise ValueError(f"VERSION {version!r} is not a supported SemVer form")
    base, pre, alpha, beta, rc = m.groups()
    if pre is None:
        return base
    if pre == "dev":
        return f"{base}.dev0"
    if alpha is not None:
        return f"{base}a{alpha}"
    if beta is not None:
        return f"{base}b{beta}"
    return f"{base}rc{rc}"


def source_root(project_root: str) -> Path:
    cli = Path(project_root)
    for candidate in (cli.parent, cli):
        if (candidate / "VERSION").is_file():
            return candidate
    raise FileNotFoundError(f"VERSION not found in {cli.parent} or {cli}")


class VersionMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict[str, Any]) -> None:
        raw = (source_root(self.root) / "VERSION").read_text(encoding="utf-8").strip()
        metadata["version"] = semver_to_pep440(raw)


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
