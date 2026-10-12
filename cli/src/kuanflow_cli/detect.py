"""Project detection and answer layering (contracts C38, C39). Detection only reads files."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kuanflow_cli.engine import content_root
from kuanflow_cli.errors import AnswersError

ANSWERS_FILE = ".copier-answers.yml"

_LEGACY = "**/legacy/**"
_MIGRATION_DIR = "src/main/resources/db/migration"
_GRADLE_FILES = ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
# agent -> (project directory, executable) (DET-05)
_AGENTS = {
    "claude": (".claude", "claude"),
    "codex": (".codex", "codex"),
    "opencode": (".opencode", "opencode"),
    "kiro": (".kiro", "kiro-cli"),
}


@dataclass(frozen=True)
class Detection:
    """What ``detect`` found: template answers, agents present, and notes on skipped files."""

    answers: dict[str, Any]
    agents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _maven(x: str) -> dict[str, str]:
    return {
        "stack": "java-maven",
        "build_cmd": f"{x} -q -DskipTests package",
        "test_cmd": f"{x} -q test",
        "verify_cmd": f"{x} -q verify",
        "single_test_cmd": f"{x} -q -Dtest={{test}} test",
        "lint_cmd": f"{x} -q spotless:check",
    }


def _gradle(x: str) -> dict[str, str]:
    return {
        "stack": "java-gradle",
        "build_cmd": f"{x} assemble",
        "test_cmd": f"{x} test",
        "verify_cmd": f"{x} check",
        "single_test_cmd": f"{x} test --tests {{test}}",
        "lint_cmd": f"{x} spotlessCheck",
    }


def _node_scripts(root: Path, notes: list[str]) -> dict[str, Any]:
    # Invalid package.json (unreadable, not UTF-8 JSON, not an object) -> no scripts plus a note.
    try:
        data = json.loads((root / "package.json").read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        notes.append(f"package.json skipped: {exc}")
        return {}
    if not isinstance(data, dict):
        notes.append("package.json skipped: not a JSON object")
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _node(root: Path, notes: list[str]) -> dict[str, str]:
    if (root / "pnpm-lock.yaml").is_file():
        pm = "pnpm"
    elif (root / "yarn.lock").is_file():
        pm = "yarn"
    else:
        pm = "npm"
    scripts = _node_scripts(root, notes)
    cmds = {"stack": "node", "test_cmd": f"{pm} test", "single_test_cmd": f"{pm} test -- {{test}}"}
    if "build" in scripts:
        cmds["build_cmd"] = f"{pm} run build"
    if "lint" in scripts:
        cmds["lint_cmd"] = f"{pm} run lint"
    cmds["verify_cmd"] = f"{pm} run verify" if "verify" in scripts else cmds["test_cmd"]
    return cmds


def _stack(root: Path, notes: list[str]) -> dict[str, str]:
    # First match wins (C38 table).
    if (root / "pom.xml").is_file() or (root / "mvnw").is_file():
        return _maven("./mvnw" if (root / "mvnw").is_file() else "mvn")
    if any((root / f).is_file() for f in (*_GRADLE_FILES, "gradlew")):
        return _gradle("./gradlew" if (root / "gradlew").is_file() else "gradle")
    if (root / "package.json").is_file():
        return _node(root, notes)
    return {"stack": "other"}


def detect(root: Path) -> Detection:
    """Guess project answers and agents from files directly in ``root`` (never fails)."""
    notes: list[str] = []
    protected = [_LEGACY]
    if (root / _MIGRATION_DIR).is_dir():
        protected.insert(0, f"{_MIGRATION_DIR}/**")
    answers: dict[str, Any] = {
        "project_name": root.name,
        **_stack(root, notes),
        "protected_paths": protected,
        "use_orca": (root / "orca.yaml").is_file() or shutil.which("orca") is not None,
    }
    agents = sorted(
        agent
        for agent, (dir_, exe) in _AGENTS.items()
        if (root / dir_).is_dir() or shutil.which(exe) is not None
    )
    return Detection(answers=answers, agents=agents, notes=notes)


def _load_mapping(path: Path) -> dict[Any, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise AnswersError(f"{path}: cannot read: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AnswersError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise AnswersError(f"{path}: must be a YAML mapping of answers")
    return data


def _questions(template: str) -> set[str]:
    config = yaml.safe_load(
        (content_root() / "templates" / template / "copier.yml").read_text(encoding="utf-8")
    )
    return {k for k in config if not k.startswith("_") and k != "kuanflow_version"}


def collect_answers(
    root: Path, *, template: str = "project", data_file: Path | None = None, personal: bool = False
) -> dict[str, Any]:
    """Answers for a render: detection < existing ``.copier-answers.yml`` < ``data_file``."""
    answers: dict[str, Any] = dict(detect(root).answers) if template == "project" else {}
    existing = root / ANSWERS_FILE
    if existing.is_file():
        answers.update(
            (k, v)
            for k, v in _load_mapping(existing).items()
            if not str(k).startswith("_") and k != "kuanflow_version"
        )
    if data_file is not None:
        data = _load_mapping(data_file)
        questions = _questions(template)
        for key in data:
            if key not in questions:
                raise AnswersError(f"{data_file}: unknown question {key!r} for template {template}")
        answers.update(data)
    if personal:
        answers["artifacts_commit"] = "none"
    return answers
