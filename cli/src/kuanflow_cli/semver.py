"""The single SemVer -> PEP 440 converter (contracts C9/C9r). Stdlib only.

Used by the root ``hatch_build.py`` (package version), ``tests/check_versions.py`` (release gate)
and the CLI at runtime. The first two load this file by path, so it must not import anything from
``kuanflow_cli``.

Allowed: ``X.Y.Z`` (no leading zeros) with an optional pre-release in one of these forms:

    dev -> .dev0     dev.N -> .devN
    alpha.N | a.N -> aN     beta.N | b.N -> bN     rc.N -> rcN

Everything else (build metadata, bare ``rc``/``alpha``/``beta``, other labels, whitespace)
raises ``ValueError``.
"""

from __future__ import annotations

import re

_NUM = r"(?:0|[1-9][0-9]*)"

_SUPPORTED = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-(?:(dev)(?:\.({_NUM}))?|(alpha|a|beta|b|rc)\.({_NUM})))?",
    re.ASCII,
)

# Full SemVer 2.0 grammar (semver.org), used only by is_semver().
_IDENT = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER = re.compile(
    rf"{_NUM}\.{_NUM}\.{_NUM}(?:-{_IDENT}(?:\.{_IDENT})*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
    re.ASCII,
)

_LABEL = {"alpha": "a", "a": "a", "beta": "b", "b": "b", "rc": "rc"}


def parse(s: str) -> tuple[int, int, int, str | None, int | None]:
    """Return ``(major, minor, patch, pre_label, pre_number)``; label is normalised (a/b/rc/dev)."""
    m = _SUPPORTED.fullmatch(s) if isinstance(s, str) else None
    if m is None:
        raise ValueError(f"not a supported SemVer version: {s!r}")
    major, minor, patch, dev, dev_n, label, n = m.groups()
    core = (int(major), int(minor), int(patch))
    if dev is not None:
        return (*core, "dev", int(dev_n or 0))
    if label is not None:
        return (*core, _LABEL[label], int(n))
    return (*core, None, None)


def is_semver(s: str) -> bool:
    """True if ``s`` is valid SemVer 2.0 (a superset of what ``parse`` accepts)."""
    return isinstance(s, str) and _SEMVER.fullmatch(s) is not None


def to_pep440(s: str) -> str:
    major, minor, patch, label, n = parse(s)
    base = f"{major}.{minor}.{patch}"
    if label is None:
        return base
    return f"{base}{'.dev' if label == 'dev' else label}{n}"
