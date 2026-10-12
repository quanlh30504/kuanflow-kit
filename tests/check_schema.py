"""Config schema check (contract C35).

Usage: ``python tests/check_schema.py`` (no arguments).

1. ``Draft202012Validator.check_schema`` on ``templates/project/schema/config.schema.json``.
2. For every ``tests/answers/*.yml``: render the project template with
   ``kuanflow_cli.engine.render`` into a temp dir and validate the rendered
   ``.kuanflow/config.yaml`` against the schema.

Exit 0 when clean; 1 with one stderr line per error, ``<answers file or schema>: <json path>:
<message>``; 2 on usage error.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "templates" / "project" / "schema" / "config.schema.json"
ANSWERS_DIR = REPO_ROOT / "tests" / "answers"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _load_schema(errors: list[str]) -> dict[str, Any] | None:
    name = _rel(SCHEMA)
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"{name}: $: cannot load schema: {_one_line(exc)}")
        return None
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        errors.append(f"{name}: {exc.json_path}: {_one_line(exc.message)}")
        return None
    if not isinstance(schema, dict):
        errors.append(f"{name}: $: schema is not an object")
        return None
    return schema


def _check_answers(path: Path, validator: Draft202012Validator, errors: list[str]) -> None:
    name = _rel(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{name}: $: cannot load answers: {_one_line(exc)}")
        return
    if not isinstance(data, dict):
        errors.append(f"{name}: $: answers file is not a mapping")
        return
    with tempfile.TemporaryDirectory(prefix="kf-check-schema-") as tmp:
        dst = Path(tmp) / "project"
        try:
            from kuanflow_cli import engine

            engine.render(dst, data)
            config = yaml.safe_load((dst / ".kuanflow" / "config.yaml").read_text(encoding="utf-8"))
        except Exception as exc:  # any render failure is reported
            errors.append(f"{name}: $: render failed: {_one_line(f'{type(exc).__name__}: {exc}')}")
            return
    for err in sorted(validator.iter_errors(config), key=lambda e: (e.json_path, e.message)):
        errors.append(f"{name}: {err.json_path}: {_one_line(err.message)}")


def main(argv: list[str]) -> int:
    if argv:
        print("usage: check_schema.py (no arguments)", file=sys.stderr)
        return 2
    errors: list[str] = []
    schema = _load_schema(errors)
    if schema is not None:
        answers = sorted(ANSWERS_DIR.glob("*.yml"))
        if not answers:
            errors.append(f"{_rel(ANSWERS_DIR)}: $: no answers files")
        validator = Draft202012Validator(schema)
        for path in answers:
            _check_answers(path, validator, errors)
    for line in errors:
        print(line, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
