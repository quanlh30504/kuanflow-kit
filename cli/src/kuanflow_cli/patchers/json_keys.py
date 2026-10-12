"""Kuanflow-managed keys in JSON files (contract C44).

Keys are dotted paths (``"permissions.deny"``); values are replaced whole. The file is
re-serialised with its original indentation, so ``remove(merge(T, m), m.keys()) == T`` for
canonically dumped ``T``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from kuanflow_cli.errors import KeysError


def _load(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise KeysError(f"invalid JSON (comments are not supported): {exc}") from None
    if not isinstance(obj, dict):
        raise KeysError(f"expected a JSON object, got {type(obj).__name__}")
    return obj


def _indent(text: str | None) -> int | str:
    # The first indented line decides: N spaces -> N, a tab -> "\t"; default 2.
    for line in (text or "").split("\n")[1:]:
        if line.startswith("\t"):
            return "\t"
        spaces = len(line) - len(line.lstrip(" "))
        if spaces:
            return spaces
    return 2


def _dump(obj: dict[str, Any], indent: int | str) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False) + "\n"


def _canonical_sha(value: Any) -> str:
    """sha256 of the canonical JSON form of a plain value (also used by ``toml_keys``)."""
    canon = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _set_key(obj: dict[str, Any], key: str, value: Any) -> None:
    """Set dotted ``key`` in a mapping, creating missing parents; ``KeysError`` on a non-object."""
    *parents, leaf = key.split(".")
    node = obj
    for i, seg in enumerate(parents):
        if seg not in node:
            node[seg] = {}
        node = node[seg]
        if not isinstance(node, dict):
            raise KeysError(f"cannot set {key!r}: {'.'.join(parents[: i + 1])!r} is not an object")
    node[leaf] = value


def _get_key(obj: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    """``(True, value)`` for a present dotted key, else ``(False, None)``."""
    node: Any = obj
    for seg in key.split("."):
        if not isinstance(node, Mapping) or seg not in node:
            return False, None
        node = node[seg]
    return True, node


def _delete_key(obj: dict[str, Any], key: str) -> None:
    """Delete dotted ``key`` (missing: no-op) and the parents this left empty."""
    segs = key.split(".")
    chain = [obj]  # chain[i] holds segs[i]
    for seg in segs[:-1]:
        node = chain[-1].get(seg)
        if not isinstance(node, dict):
            return
        chain.append(node)
    if segs[-1] not in chain[-1]:
        return
    del chain[-1][segs[-1]]
    # Prune only parents emptied by this deletion; objects that were already empty stay.
    for depth in range(len(chain) - 1, 0, -1):
        if chain[depth]:
            break
        del chain[depth - 1][segs[depth - 1]]


def merge(text: str | None, managed: Mapping[str, Any]) -> str:
    """Set each managed key in the JSON object ``text`` (``None``/``""`` = no file)."""
    obj = _load(text)
    for key, value in managed.items():
        _set_key(obj, key, value)
    return _dump(obj, _indent(text))


def remove(text: str, keys: Iterable[str]) -> str:
    """Delete ``keys`` from the JSON object ``text`` and prune parents they left empty."""
    obj = _load(text)
    for key in keys:
        _delete_key(obj, key)
    return _dump(obj, _indent(text))


def values_sha(text: str | None, keys: Iterable[str]) -> dict[str, str | None]:
    """Canonical sha256 per key of its current value, ``None`` when absent."""
    obj = _load(text)
    out: dict[str, str | None] = {}
    for key in keys:
        present, value = _get_key(obj, key)
        out[key] = _canonical_sha(value) if present else None
    return out
