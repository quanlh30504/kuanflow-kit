"""Static checks for plugin content (contracts C5, C16).

Usage: python tests/check_skills.py <plugin_dir>
Exit 0 when clean, 1 on violations (one stderr line each), 2 on usage error.

Rules are plain functions listed in RULES:
  S1 skill frontmatter · S2 agent frontmatter + tool allowlist · S3 command frontmatter ·
  S4 no hard-coded build commands · S5 banned prompt/TLS/network patterns.
"""

from __future__ import annotations

import argparse
import re
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
    line: int | None = None

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"{where}: {self.message}"


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


MAX_DESCRIPTION = 1024
TOOL_ALLOWLIST = {"Read", "Grep", "Glob", "Bash", "Write", "Edit", "WebFetch", "WebSearch"}
# Q-05: research, review and RCA roles never get write access.
READ_ONLY_AGENTS = {
    "codebase-locator",
    "codebase-analyzer",
    "pattern-finder",
    "adversarial-reviewer",
}
READ_ONLY_PREFIXES = ("rca-",)
WRITE_TOOLS = {"Write", "Edit"}

HARD_CODED = re.compile(r"mvnw|gradlew|npm run|\bmvn\s")
EXAMPLE_MARKER = "<!-- kuanflow:example -->"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")

PLACEHOLDER_HOST = re.compile(
    r"^(<[^>]*>.*|localhost|127\.0\.0\.1|(.+\.)?example\.(com|org|net))(:\d+)?$", re.IGNORECASE
)
BANNED: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "prompt-injection phrase"),
    (re.compile(r"verify\s*=\s*False"), "disables TLS verification"),
    (re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*0"), "disables TLS verification"),
    (
        re.compile(r"\b(curl|wget)\b.*\s(-k|--insecure|--no-check-certificate)(\s|$)"),
        "disables TLS verification",
    ),
)
NETWORK_URL = re.compile(r"\b(curl|wget)\b.*?\bhttps?://([^/\s\"')]+)")


def _load(path: Path) -> tuple[dict | None, Violation | None]:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, FrontmatterError) as exc:
        return None, Violation(path, str(exc))


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def rule_skill_frontmatter(plugin: Path) -> Iterator[Violation]:
    """S1: skills/<name>/SKILL.md has name == <name> and a description of 1..1024 chars."""
    for skill_md in sorted(plugin.glob("skills/*/SKILL.md")):
        dirname = skill_md.parent.name
        meta, err = _load(skill_md)
        if err:
            yield err
            continue
        name = meta.get("name")
        if name != dirname:
            yield Violation(skill_md, f"frontmatter name {name!r} != directory {dirname!r}")
        desc = meta.get("description")
        if not _nonempty_str(desc):
            yield Violation(skill_md, "frontmatter description is missing or empty")
        elif len(desc) > MAX_DESCRIPTION:
            yield Violation(
                skill_md, f"frontmatter description is {len(desc)} chars (max {MAX_DESCRIPTION})"
            )


def _tools(value: object) -> list[str] | None:
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    if isinstance(value, list) and all(isinstance(t, str) for t in value):
        return [t.strip() for t in value]
    return None


def rule_agent_frontmatter(plugin: Path) -> Iterator[Violation]:
    """S2: agents/<name>.md has name == <name>, a description, and tools from the allowlist."""
    for agent_md in sorted(plugin.glob("agents/*.md")):
        stem = agent_md.stem
        meta, err = _load(agent_md)
        if err:
            yield err
            continue
        problems = []
        if meta.get("name") != stem:
            problems.append(f"frontmatter name {meta.get('name')!r} != file name {stem!r}")
        if not _nonempty_str(meta.get("description")):
            problems.append("frontmatter description is missing or empty")
        tools = _tools(meta.get("tools"))
        if not tools:
            problems.append("frontmatter tools is missing or empty")
        else:
            unknown = [t for t in tools if t not in TOOL_ALLOWLIST]
            if unknown:
                problems.append(f"tools outside the allowlist: {', '.join(unknown)}")
            read_only = stem in READ_ONLY_AGENTS or stem.startswith(READ_ONLY_PREFIXES)
            granted = sorted(WRITE_TOOLS & set(tools))
            if read_only and granted:
                problems.append(f"read-only agent {stem!r} must not have {', '.join(granted)}")
        if problems:
            yield Violation(agent_md, "; ".join(problems))


def rule_command_frontmatter(plugin: Path) -> Iterator[Violation]:
    """S3: commands/<name>.md has frontmatter with a non-empty description."""
    for cmd_md in sorted(plugin.glob("commands/*.md")):
        meta, err = _load(cmd_md)
        if err:
            yield err
        elif not _nonempty_str(meta.get("description")):
            yield Violation(cmd_md, "frontmatter description is missing or empty")


def _text_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            try:
                path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield path


def _checked_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield (line number, line) outside fenced blocks marked with EXAMPLE_MARKER."""
    lines = text.splitlines()
    exempt_fence: str | None = None
    marker_pending = False
    for no, line in enumerate(lines, start=1):
        fence = FENCE.match(line)
        if exempt_fence is not None:
            if (
                fence
                and fence.group(1)[0] == exempt_fence[0]
                and len(fence.group(1)) >= len(exempt_fence)
            ):
                exempt_fence = None
            continue
        if marker_pending and fence:
            exempt_fence = fence.group(1)
            marker_pending = False
            continue
        if line.strip() == EXAMPLE_MARKER:
            marker_pending = True
            continue
        if line.strip():
            marker_pending = False
        yield no, line


def rule_no_hard_coded_commands(plugin: Path) -> Iterator[Violation]:
    """S4: skills/agents/commands use config keys, never literal build commands."""
    for sub in ("skills", "agents", "commands"):
        for path in _text_files(plugin / sub):
            for no, line in _checked_lines(path.read_text(encoding="utf-8")):
                m = HARD_CODED.search(line)
                if m:
                    yield Violation(
                        path,
                        f"hard-coded build command {m.group(0).strip()!r} (use commands.* keys)",
                        no,
                    )


def rule_banned_patterns(plugin: Path) -> Iterator[Violation]:
    """S5: no prompt-injection phrases, TLS disabling, or downloads from real hosts."""
    for path in _text_files(plugin):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern, why in BANNED:
                if pattern.search(line):
                    yield Violation(path, f"banned pattern ({why})", no)
                    break
            else:
                for m in NETWORK_URL.finditer(line):
                    if not PLACEHOLDER_HOST.match(m.group(2)):
                        yield Violation(
                            path, f"network call to non-placeholder host {m.group(2)!r}", no
                        )
                        break


RULES: tuple[Rule, ...] = (
    rule_skill_frontmatter,
    rule_agent_frontmatter,
    rule_command_frontmatter,
    rule_no_hard_coded_commands,
    rule_banned_patterns,
)


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
