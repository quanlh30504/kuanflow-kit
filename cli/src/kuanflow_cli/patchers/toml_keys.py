"""Kuanflow-managed keys in TOML files (contract C45), via tomlkit so untouched parts keep
their comments, order and formatting. Same API and key rules as ``json_keys``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.toml_document import TOMLDocument

from kuanflow_cli.errors import KeysError
from kuanflow_cli.patchers.json_keys import _canonical_sha, _delete_key, _get_key, _set_key


def _load(text: str | None) -> TOMLDocument:
    try:
        return tomlkit.parse(text or "")
    except TOMLKitError as exc:
        raise KeysError(f"invalid TOML: {exc}") from None


def merge(text: str | None, managed: Mapping[str, Any]) -> str:
    """Set each managed key (``a.b`` = key ``b`` in table ``a``); ``None``/``""`` = no file."""
    doc = _load(text)
    if not managed:
        return text or ""
    for key, value in managed.items():
        _set_key(doc, key, value)
    return tomlkit.dumps(doc)


def remove(text: str, keys: Iterable[str]) -> str:
    """Delete ``keys`` and prune the tables they left empty."""
    doc = _load(text)
    for key in keys:
        _delete_key(doc, key)
    out = tomlkit.dumps(doc)
    # tomlkit keeps the blank line it put before an appended table after that table is pruned;
    # never leave a trailing blank line the input did not have (round trip with ``merge``).
    if out.endswith("\n\n") and not text.endswith("\n\n"):
        out = out.rstrip("\n") + "\n" if out.strip("\n") else ""
    return out


def values_sha(text: str | None, keys: Iterable[str]) -> dict[str, str | None]:
    """Canonical JSON sha256 per key of its plain value, ``None`` when absent."""
    doc = _load(text).unwrap()
    out: dict[str, str | None] = {}
    for key in keys:
        present, value = _get_key(doc, key)
        out[key] = _canonical_sha(value) if present else None
    return out
