"""Static checks for plugin content (contract C5, P1 stub).

Usage: python tests/check_skills.py <plugin_dir>
Exit 0 when clean, 1 on violations (one stderr line each), 2 on usage error.

Rules are plain functions listed in RULES; later phases add agent/command/hard-coded-command
rules by appending functions, without touching the driver.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:  # optional dependency
    yaml = None


class FrontmatterError(ValueError):
    pass


@dataclass(frozen=True)
class Violation:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _simple_yaml(text: str) -> dict[str, str]:
    # Fallback for flat `key: value` frontmatter when PyYAML is unavailable.
    data: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw[0] in " \t-":
            continue
        key, sep, value = raw.partition(":")
        if not sep:
            raise FrontmatterError(f"cannot parse frontmatter line {raw!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        data[key.strip()] = value
    return data


def parse_frontmatter(text: str) -> dict:
    """Return the mapping between the leading `---` lines; raise FrontmatterError if absent/bad."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("missing frontmatter (file must start with '---')")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise FrontmatterError("unterminated frontmatter (no closing '---')")
    body = "\n".join(lines[1:end])
    if yaml is not None:
        try:
            data = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            raise FrontmatterError(f"invalid YAML frontmatter: {exc}") from exc
    else:
        data = _simple_yaml(body)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data


Rule = Callable[[Path], Iterator[Violation]]


def rule_skill_frontmatter(plugin: Path) -> Iterator[Violation]:
    """skills/<name>/SKILL.md needs frontmatter with name == <name> and a non-empty description."""
    for skill_md in sorted(plugin.glob("skills/*/SKILL.md")):
        dirname = skill_md.parent.name
        try:
            meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, FrontmatterError) as exc:
            yield Violation(skill_md, str(exc))
            continue
        name = meta.get("name")
        if name != dirname:
            yield Violation(skill_md, f"frontmatter name {name!r} != directory {dirname!r}")
        desc = meta.get("description")
        if not isinstance(desc, str) or not desc.strip():
            yield Violation(skill_md, "frontmatter description is missing or empty")


RULES: tuple[Rule, ...] = (rule_skill_frontmatter,)


def check(plugin: Path, rules: tuple[Rule, ...] = RULES) -> list[Violation]:
    return [v for rule in rules for v in rule(plugin)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static checks for a Kuanflow plugin directory.")
    parser.add_argument("plugin_dir", type=Path)
    args = parser.parse_args(argv)  # missing argument -> exit 2
    if not args.plugin_dir.is_dir():
        print(f"{args.plugin_dir}: not a directory", file=sys.stderr)
        return 1
    violations = check(args.plugin_dir)
    for v in violations:
        print(v, file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
