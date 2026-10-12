#!/usr/bin/env python3
"""Build the level-1 index of the knowledge repo as JSON.

Output: ``{"version": 1, "entries": [...]}``, entries sorted by ``path``:

- every postmortem (``postmortems/**/*.md`` except ``README.md``) with valid frontmatter, as
  ``{"kind": "postmortem", "path", "id", "title", "date", "severity", "services", "category",
  "signatures", "status"}``; missing optional keys are null, dates are ISO strings;
- every shared runbook (``runbooks-shared/**/*.md`` except ``README.md``) as
  ``{"kind": "runbook", "path", "title"}``; the title is the frontmatter ``title``, else the
  first ``# `` heading, else the file name without extension.

Postmortems with missing or invalid frontmatter are skipped with one warning each on stderr.
Exit 0, or 2 when ``--root`` is not a directory or ``--out`` cannot be written. The same tree
always gives the same bytes.

Requires Python 3.11+ and PyYAML. The validation rules come from ``check-frontmatter.py`` in
the same directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

INDEX_VERSION = 1
POSTMORTEM_KEYS = (
    "id",
    "title",
    "date",
    "severity",
    "services",
    "category",
    "signatures",
    "status",
)


def _load_checker() -> Any:
    """Load the sibling ``check-frontmatter.py`` (its name is not an importable module name)."""
    path = Path(__file__).resolve().with_name("check-frontmatter.py")
    spec = importlib.util.spec_from_file_location("kuanflow_check_frontmatter", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _json_value(value: Any) -> Any:
    """Make a frontmatter value JSON-serialisable without losing its meaning."""
    if isinstance(value, dt.date):  # also datetime
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def postmortem_entries(root: Path, categories: list[str] | None) -> list[dict[str, Any]]:
    entries = []
    for path in checker.postmortem_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            fm = checker.read_frontmatter(path)
        except checker.FrontmatterError as exc:
            print(f"warning: {rel}: skipped: {exc}", file=sys.stderr)
            continue
        problems = checker.validate(fm, categories)
        if problems:
            print(f"warning: {rel}: skipped: {'; '.join(problems)}", file=sys.stderr)
            continue
        entry: dict[str, Any] = {"kind": "postmortem", "path": rel}
        entry.update({key: _json_value(fm.get(key)) for key in POSTMORTEM_KEYS})
        entries.append(entry)
    return entries


def runbook_title(path: Path) -> str:
    try:
        fm = checker.read_frontmatter(path)
    except checker.FrontmatterError:
        fm = {}
    title = fm.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        text = ""
    for line in text.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return path.stem


def runbook_entries(root: Path) -> list[dict[str, Any]]:
    base = root / "runbooks-shared"
    if not base.is_dir():
        return []
    files = [p for p in base.rglob("*.md") if p.is_file() and p.name != "README.md"]
    return [
        {"kind": "runbook", "path": p.relative_to(root).as_posix(), "title": runbook_title(p)}
        for p in files
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the level-1 knowledge index (JSON).")
    parser.add_argument(
        "--root", type=Path, default=Path("."), help="knowledge repo root (default: cwd)"
    )
    parser.add_argument("--out", type=Path, help="write the index to FILE instead of stdout")
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return 2

    categories = checker.load_categories(root)
    if not categories:
        print(
            "warning: taxonomy.md missing or without categories; "
            "postmortem categories are not checked against it",
            file=sys.stderr,
        )
        categories = None

    entries = postmortem_entries(root, categories) + runbook_entries(root)
    entries.sort(key=lambda e: e["path"])
    index = {"version": INDEX_VERSION, "entries": entries}
    data = (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.out is None:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()
        return 0
    try:
        args.out.write_bytes(data)
    except OSError as exc:
        print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
