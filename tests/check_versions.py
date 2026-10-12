"""Check that every version source in the repo agrees with VERSION (contract C4).

Usage: python tests/check_versions.py [--root DIR] [--tag vX.Y.Z[-pre]]
Exit 0 when all present sources agree, 1 otherwise (one stderr line per problem).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

# Official SemVer 2.0 regex (semver.org), without a leading "v".
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# SemVer prerelease label -> PEP 440 suffix.
_PRE_LABELS = {"dev": ".dev", "alpha": "a", "a": "a", "beta": "b", "b": "b", "rc": "rc"}
_PRE_RE = re.compile(r"^(dev|alpha|a|beta|b|rc)(?:\.(0|[1-9]\d*))?$")

PLUGIN_JSON = Path("plugins/kuanflow/.claude-plugin/plugin.json")
MARKETPLACE_JSON = Path(".claude-plugin/marketplace.json")
CLI_PYPROJECT = Path("cli/pyproject.toml")


class VersionError(ValueError):
    pass


def semver_to_pep440(version: str) -> str:
    """Map SemVer to PEP 440, e.g. 0.1.0-dev -> 0.1.0.dev0, 1.2.0-rc.1 -> 1.2.0rc1."""
    m = SEMVER_RE.match(version)
    if not m:
        raise VersionError(f"not a valid SemVer: {version!r}")
    if m.group(5):
        raise VersionError(f"build metadata is not supported: {version!r}")
    release = ".".join(m.group(i) for i in (1, 2, 3))
    pre = m.group(4)
    if pre is None:
        return release
    pm = _PRE_RE.match(pre)
    if not pm:
        raise VersionError(f"unsupported prerelease form {pre!r} in {version!r}")
    return f"{release}{_PRE_LABELS[pm.group(1)]}{pm.group(2) or '0'}"


def _normalise_pep440(value: str) -> str:
    # A static pyproject version may be written in SemVer or PEP 440 form.
    value = value.strip()
    if SEMVER_RE.match(value):
        return semver_to_pep440(value)
    return value.lower()


def read_version(root: Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise VersionError(f"VERSION: file not found at {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    version = lines[0].strip() if lines else ""
    if not SEMVER_RE.match(version):
        raise VersionError(f"VERSION: not a valid SemVer: {version!r}")
    return version


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"{path}: cannot read: {exc}") from exc


def check_plugin(root: Path, version: str) -> list[str]:
    path = root / PLUGIN_JSON
    if not path.is_file():
        return []
    found = _load_json(path).get("version")
    if found != version:
        return [f"{PLUGIN_JSON}: version {found!r} != VERSION {version!r}"]
    return []


def check_marketplace(root: Path, version: str) -> list[str]:
    path = root / MARKETPLACE_JSON
    if not path.is_file():
        return []
    data = _load_json(path)
    errors = []
    meta = (data.get("metadata") or {}).get("version")
    if meta != version:
        errors.append(f"{MARKETPLACE_JSON}: metadata.version {meta!r} != VERSION {version!r}")
    entries = [p for p in data.get("plugins") or [] if p.get("name") == "kuanflow"]
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
        return []  # derived from VERSION at build time: consistent by construction
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
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1], help="repo root"
    )
    parser.add_argument("--tag", help="release tag that must equal 'v' + VERSION")
    args = parser.parse_args(argv)
    errors = run(args.root, args.tag)
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
