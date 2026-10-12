"""Install manifest ``.kuanflow/manifest.json`` (C40): model, strict read, canonical dump."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kuanflow_cli.errors import ManifestError

MANIFEST_PATH = Path(".kuanflow/manifest.json")
DEFAULT_SOURCE = "git+https://github.com/<org>/kuanflow.git"

# Per-owner entry fields after "path" and "owner", in output order; "agent" (optional) comes last.
_OWNER_FIELDS: dict[str, tuple[str, ...]] = {
    "template-managed": ("sha256",),
    "merge-required": ("sha256",),
    "local-owned": ("sha256",),
    "managed-block": ("block", "sha256", "created"),
    "managed-keys": ("keys", "created"),
}
_FIELD_TYPES: dict[str, type] = {"sha256": str, "block": str, "keys": dict, "created": bool}


@dataclass(kw_only=True)
class FileEntry:
    """One file Kuanflow wrote; only the fields of its ``owner`` are set."""

    path: str
    owner: str
    sha256: str | None = None
    block: str | None = None
    keys: dict[str, str] | None = None
    created: bool | None = None
    agent: str | None = None


@dataclass(kw_only=True)
class Manifest:
    """The manifest document; ``source`` defaults to ``KUANFLOW_SOURCE`` + ``@v<version>``."""

    kuanflow_version: str
    template: str
    installed_at: str
    mode: str
    agents: list[str]
    files: list[FileEntry]
    manifest_version: int = 1
    updated_at: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.source is None:
            base = os.environ.get("KUANFLOW_SOURCE") or DEFAULT_SOURCE
            self.source = f"{base}@v{self.kuanflow_version}"


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def _entry_dict(entry: FileEntry) -> dict[str, Any]:
    out: dict[str, Any] = {"path": entry.path, "owner": entry.owner}
    for name in _OWNER_FIELDS[entry.owner]:
        out[name] = getattr(entry, name)
    if entry.agent is not None:
        out["agent"] = entry.agent
    return out


def dumps(m: Manifest) -> str:
    """Canonical JSON text: fixed key order, files sorted by path, trailing newline."""
    data: dict[str, Any] = {
        "manifest_version": m.manifest_version,
        "kuanflow_version": m.kuanflow_version,
        "template": m.template,
        "installed_at": m.installed_at,
    }
    if m.updated_at is not None:
        data["updated_at"] = m.updated_at
    data["mode"] = m.mode
    data["agents"] = list(m.agents)
    data["source"] = m.source
    data["files"] = [_entry_dict(e) for e in sorted(m.files, key=lambda e: e.path)]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _get(obj: dict[str, Any], key: str, kind: type, where: str, *, optional: bool = False) -> Any:
    if key not in obj and optional:
        return None
    value = obj.get(key)
    # type() rather than isinstance(): a bool is not an int here, and vice versa.
    if key not in obj or type(value) is not kind:
        raise ManifestError(f"{where}: {key!r} must be a {kind.__name__}")
    return value


def _entry(obj: Any, where: str) -> FileEntry:
    if not isinstance(obj, dict):
        raise ManifestError(f"{where}: file entry must be an object")
    path = _get(obj, "path", str, where)
    owner = obj.get("owner")
    if not isinstance(owner, str) or owner not in _OWNER_FIELDS:
        raise ManifestError(f"{where}: {path}: unknown owner {owner!r}")
    fields = {
        name: _get(obj, name, _FIELD_TYPES[name], f"{where}: {path}")
        for name in _OWNER_FIELDS[owner]
    }
    keys = fields.get("keys")
    if keys is not None and not all(isinstance(v, str) for v in keys.values()):
        raise ManifestError(f"{where}: {path}: 'keys' values must be strings")
    agent = _get(obj, "agent", str, f"{where}: {path}", optional=True)
    return FileEntry(path=path, owner=owner, agent=agent, **fields)


def read(root: Path) -> Manifest | None:
    """Load and validate ``<root>/.kuanflow/manifest.json``; ``None`` when there is none."""
    file = root / MANIFEST_PATH
    if not file.is_file():
        return None
    where = str(file)
    try:
        data = json.loads(file.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"{where}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{where}: must be a JSON object")
    if _get(data, "manifest_version", int, where) != 1:
        raise ManifestError(f"{where}: unsupported manifest_version {data['manifest_version']}")
    agents = _get(data, "agents", list, where)
    if not all(isinstance(a, str) for a in agents):
        raise ManifestError(f"{where}: 'agents' must be a list of strings")
    files = [_entry(e, where) for e in _get(data, "files", list, where)]
    paths = [e.path for e in files]
    if len(set(paths)) != len(paths):
        raise ManifestError(f"{where}: duplicate file paths")
    return Manifest(
        kuanflow_version=_get(data, "kuanflow_version", str, where),
        template=_get(data, "template", str, where),
        installed_at=_get(data, "installed_at", str, where),
        updated_at=_get(data, "updated_at", str, where, optional=True),
        mode=_get(data, "mode", str, where),
        agents=agents,
        source=_get(data, "source", str, where),
        files=files,
    )


def write(root: Path, m: Manifest) -> None:
    """Write ``dumps(m)`` to ``<root>/.kuanflow/manifest.json``."""
    file = root / MANIFEST_PATH
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(dumps(m).encode("utf-8"))


def diff(old: Manifest, new: Manifest) -> dict[str, list[str]]:
    """Paths ``added``, ``removed`` and ``changed`` (any field differs) from ``old`` to ``new``."""
    before = {e.path: e for e in old.files}
    after = {e.path: e for e in new.files}
    return {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "changed": sorted(p for p in before.keys() & after.keys() if before[p] != after[p]),
    }
