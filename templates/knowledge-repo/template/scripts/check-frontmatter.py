#!/usr/bin/env python3
"""Validate the YAML frontmatter of every postmortem in the knowledge repo.

Checks every ``postmortems/**/*.md`` except files named ``README.md``. Required keys:
``id`` (non-empty string), ``services`` (non-empty list of non-empty strings), ``category``
(one of the categories in ``taxonomy.md``), ``signatures`` (non-empty list of strings) and
``status`` (``draft`` or ``approved``).

Prints one line per problem to stderr: ``<path relative to root>: <message>``.
Exit 0 when everything is valid, 1 on any problem, 2 when ``taxonomy.md`` is missing or
lists no categories.

Requires Python 3.11+ and PyYAML. Also used as a module by ``build-index.py``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

STATUSES = ("draft", "approved")
_CATEGORY_LINE = re.compile(r"-\s+`([^`]+)`\s*")


class FrontmatterError(Exception):
    """The file has no parsable frontmatter mapping."""


def load_categories(root: Path) -> list[str] | None:
    """Return the categories listed under ``## Categories`` in ``taxonomy.md``.

    Returns None when the file is missing or unreadable, and an empty list when it has no
    categories.
    """
    try:
        lines = (root / "taxonomy.md").read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    categories: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = stripped == "## Categories"
            continue
        if in_section:
            match = _CATEGORY_LINE.fullmatch(stripped)
            if match:
                categories.append(match.group(1))
    return categories


def postmortem_files(root: Path) -> list[Path]:
    """All postmortem files under ``root``, sorted by relative POSIX path."""
    base = root / "postmortems"
    if not base.is_dir():
        return []
    files = [p for p in base.rglob("*.md") if p.is_file() and p.name != "README.md"]
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def read_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the leading ``---`` YAML block of ``path`` into a mapping."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise FrontmatterError(f"cannot read file ({exc})") from exc
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise FrontmatterError("missing frontmatter (the file must start with a '---' line)")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        raise FrontmatterError("frontmatter is not closed (no second '---' line)")
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        reason = " ".join(str(exc).split())
        raise FrontmatterError(f"frontmatter is not valid YAML ({reason})") from exc
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate(fm: dict[str, Any], categories: list[str] | None) -> list[str]:
    """Return one message per problem in ``fm``; each message names its field.

    With ``categories`` None, ``category`` is only checked to be a non-empty string.
    """
    problems: list[str] = []

    def check(field: str, ok: bool, rule: str) -> None:
        if field not in fm:
            problems.append(f"{field}: missing required field")
        elif not ok:
            problems.append(f"{field}: must be {rule} (got {fm[field]!r})")

    check("id", _is_text(fm.get("id")), "a non-empty string")
    services = fm.get("services")
    check(
        "services",
        isinstance(services, list) and bool(services) and all(_is_text(s) for s in services),
        "a non-empty list of non-empty strings",
    )
    category = fm.get("category")
    if categories is None:
        check("category", _is_text(category), "a non-empty string")
    else:
        check("category", category in categories, "one of the categories in taxonomy.md")
    signatures = fm.get("signatures")
    check(
        "signatures",
        isinstance(signatures, list)
        and bool(signatures)
        and all(isinstance(s, str) for s in signatures),
        "a non-empty list of strings",
    )
    check("status", fm.get("status") in STATUSES, "one of: " + ", ".join(STATUSES))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate postmortem frontmatter.")
    parser.add_argument(
        "--root", type=Path, default=Path("."), help="knowledge repo root (default: cwd)"
    )
    args = parser.parse_args(argv)
    root: Path = args.root

    categories = load_categories(root)
    if categories is None:
        print(f"error: {root / 'taxonomy.md'} not found or unreadable", file=sys.stderr)
        return 2
    if not categories:
        print(
            f"error: {root / 'taxonomy.md'} lists no categories under '## Categories'",
            file=sys.stderr,
        )
        return 2

    failed = False
    for path in postmortem_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            problems = validate(read_frontmatter(path), categories)
        except FrontmatterError as exc:
            problems = [str(exc)]
        for problem in problems:
            print(f"{rel}: {problem}", file=sys.stderr)
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
