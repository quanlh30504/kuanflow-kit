"""Check that every version source in the repo agrees with VERSION (contract C4).

Usage: python tests/check_versions.py [--root DIR] [--tag vX.Y.Z[-pre]]
Exit 0 when all present sources agree, 1 otherwise (one stderr line per problem).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]

PLUGIN_JSON = Path("plugins/kuanflow/.claude-plugin/plugin.json")
MARKETPLACE_JSON = Path(".claude-plugin/marketplace.json")
CLI_PYPROJECT = Path("cli/pyproject.toml")


def _load_semver() -> ModuleType:
    # The one SemVer -> PEP 440 converter (contract C9), shared with cli/hatch_build.py.
    path = REPO_ROOT / "cli" / "semver_pep440.py"
    spec = importlib.util.spec_from_file_location("_kuanflow_semver_pep440", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semver_pep440 = _load_semver()


class VersionError(ValueError):
    pass


def semver_to_pep440(version: str) -> str:
    try:
        return semver_pep440.to_pep440(version)
    except ValueError as exc:
        raise VersionError(str(exc)) from exc


def _normalise_pep440(value: str) -> str:
    # A static pyproject version may be written in SemVer or PEP 440 form.
    value = value.strip()
    if semver_pep440.is_semver(value):
        return semver_to_pep440(value)
    return value.lower()


def read_version(root: Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise VersionError(f"VERSION: file not found at {path}")
    text = path.read_text(encoding="utf-8")
    version = text[:-1] if text.endswith("\n") else text
    if not version or "\n" in version or "\r" in version:
        raise VersionError("VERSION: must be exactly one line")
    if not semver_pep440.is_semver(version):
        raise VersionError(f"VERSION: not a valid SemVer: {version!r}")
    return version


def _load_json(path: Path, rel: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VersionError(f"{rel}: cannot read: {exc}") from exc
    if not isinstance(data, dict):
        raise VersionError(f"{rel}: top level must be a JSON object, got {type(data).__name__}")
    return data


def check_plugin(root: Path, version: str) -> list[str]:
    path = root / PLUGIN_JSON
    if not path.is_file():
        return []
    found = _load_json(path, PLUGIN_JSON).get("version")
    if found != version:
        return [f"{PLUGIN_JSON}: version {found!r} != VERSION {version!r}"]
    return []


def check_marketplace(root: Path, version: str) -> list[str]:
    path = root / MARKETPLACE_JSON
    if not path.is_file():
        return []
    data = _load_json(path, MARKETPLACE_JSON)
    errors = []
    metadata = data.get("metadata")
    meta = metadata.get("version") if isinstance(metadata, dict) else None
    if meta != version:
        errors.append(f"{MARKETPLACE_JSON}: metadata.version {meta!r} != VERSION {version!r}")
    plugins = data.get("plugins")
    plugins = plugins if isinstance(plugins, list) else []
    entries = [p for p in plugins if isinstance(p, dict) and p.get("name") == "kuanflow"]
    if not entries:
        errors.append(f"{MARKETPLACE_JSON}: no plugins[] entry named 'kuanflow'")
    for entry in entries:
        found = entry.get("version")
        if found != version:
            errors.append(
                f"{MARKETPLACE_JSON}: plugins[kuanflow].version {found!r} != VERSION {version!r}"
            )
    return errors


def check_cli(root: Path, version: str) -> list[str]:
    path = root / CLI_PYPROJECT
    if not path.is_file():
        return []
    try:
        project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
    except tomllib.TOMLDecodeError as exc:
        return [f"{CLI_PYPROJECT}: invalid TOML: {exc}"]
    if "version" in project.get("dynamic", []):
        return []  # hatch_build.py derives it from VERSION via the same converter
    static = project.get("version")
    if static is None:
        return [f"{CLI_PYPROJECT}: [project] has neither a static nor a dynamic version"]
    expected = semver_to_pep440(version)
    try:
        found = _normalise_pep440(str(static))
    except VersionError as exc:
        return [f"{CLI_PYPROJECT}: {exc}"]
    if found != expected:
        return [f"{CLI_PYPROJECT}: version {static!r} != {expected!r} (from VERSION {version!r})"]
    return []


def check_tag(tag: str, version: str) -> list[str]:
    if tag != f"v{version}":
        return [f"tag {tag!r} != 'v' + VERSION ('v{version}')"]
    return []


# Each check takes (root, version) and returns a list of problems; later sources append here.
CHECKS = (check_plugin, check_marketplace, check_cli)


def run(root: Path, tag: str | None = None) -> list[str]:
    try:
        version = read_version(root)
        semver_to_pep440(version)  # reject prerelease forms the CLI package cannot publish
    except VersionError as exc:
        return [str(exc)]
    errors: list[str] = []
    for check in CHECKS:
        try:
            errors.extend(check(root, version))
        except VersionError as exc:
            errors.append(str(exc))
    if tag is not None:
        errors.extend(check_tag(tag, version))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that all version sources agree.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repo root")
    parser.add_argument("--tag", help="release tag that must equal 'v' + VERSION")
    args = parser.parse_args(argv)
    errors = run(args.root, args.tag)
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
