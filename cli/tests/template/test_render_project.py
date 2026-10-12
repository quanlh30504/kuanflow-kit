"""Contract tests C25 (render result), C26, C27, C28: the project template, rendered."""

from __future__ import annotations

import importlib
import json
import os
import re
import stat
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "project"
COPIER_YML = TEMPLATE / "copier.yml"
SCHEMA = TEMPLATE / "schema" / "config.schema.json"
ANSWERS_DIR = REPO_ROOT / "tests" / "answers"
PLUGIN_SCRIPTS = REPO_ROOT / "plugins" / "kuanflow" / "scripts"

STACKS = ["java-maven", "java-gradle", "node", "python", "other"]
SCRIPTS = ["load-config.sh", "guard-bash.sh", "guard-protected-paths.sh"]
CACHE = ".kuanflow/cache/template-repo"

MAKE_DEFAULTS = {
    "build": "make build",
    "test": "make test",
    "verify": "make verify",
    "single_test": "make test TEST={test}",
    "lint": "make lint",
}
STACK_DEFAULTS: dict[str, dict[str, str]] = {
    "java-maven": {
        "build": "./mvnw -q -DskipTests package",
        "test": "./mvnw -q test",
        "verify": "./mvnw -q verify",
        "single_test": "./mvnw -q -Dtest={test} test",
        "lint": "./mvnw -q spotless:check",
    },
    "java-gradle": {
        "build": "./gradlew assemble",
        "test": "./gradlew test",
        "verify": "./gradlew check",
        "single_test": "./gradlew test --tests {test}",
        "lint": "./gradlew spotlessCheck",
    },
    "node": MAKE_DEFAULTS,
    "python": MAKE_DEFAULTS,
    "other": MAKE_DEFAULTS,
}

QUESTIONS = {
    "project_name",
    "stack",
    "build_cmd",
    "test_cmd",
    "verify_cmd",
    "single_test_cmd",
    "lint_cmd",
    "ticket_pattern",
    "fintech",
    "protected_paths",
    "services",
    "artifacts_commit",
    "use_orca",
    "knowledge_repo",
    "jira_project_key",
    "kuanflow_version",
}

BASE_TREE = {
    ".copier-answers.yml",
    ".kuanflow/config.yaml",
    ".kuanflow/README.md",
    ".kuanflow/templates/.gitkeep",
    *(f".kuanflow/scripts/{s}" for s in SCRIPTS),
    "kuan-workbench/work/.gitkeep",
    "kuan-workbench/wiki/.gitkeep",
    "docs/adr/0000-template.md",
    "docs/runbooks/README.md",
}

# Vietnamese-only letters (the docs the templates are derived from are in Vietnamese).
_VI_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯ")


def engine() -> ModuleType:
    return importlib.import_module("kuanflow_cli.engine")


def load_answers(stack: str) -> dict[str, Any]:
    data = yaml.safe_load((ANSWERS_DIR / f"{stack}.yml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def current_version() -> str:
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def tree(root: Path) -> set[str]:
    out = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if rel == ".kuanflow/cache" or rel.startswith(".kuanflow/cache/"):
            continue
        if p.is_file() or p.is_symlink():
            out.add(rel)
    return out


def is_english(text: str) -> bool:
    if any(c in _VI_CHARS for c in text):
        return False
    return not any(0x1EA0 <= ord(c) <= 0x1EF9 for c in text)


def frontmatter(text: str) -> dict[str, Any]:
    assert text.startswith("---\n"), "missing frontmatter"
    end = text.index("\n---\n", 4)
    data = yaml.safe_load(text[4:end])
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    eng = engine()
    out: dict[str, Path] = {}
    for stack in STACKS:
        dst = tmp_path_factory.mktemp(f"render-{stack}") / "proj"
        eng.render(dst, load_answers(stack))
        out[stack] = dst
    return out


def config(dst: Path) -> dict[str, Any]:
    data = yaml.safe_load((dst / ".kuanflow" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def answers_file(dst: Path) -> dict[str, Any]:
    data = yaml.safe_load((dst / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


# --- C26 copier.yml ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def copier_yml() -> dict[str, Any]:
    data = yaml.safe_load(COPIER_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _choices(q: dict[str, Any]) -> list[Any]:
    ch = q.get("choices")
    if isinstance(ch, dict):
        return list(ch.values())
    assert isinstance(ch, list), q
    return ch


def _default(q: dict[str, Any]) -> Any:
    d = q.get("default")
    if q.get("type") == "yaml" and isinstance(d, str):
        return yaml.safe_load(d)
    return d


def test_c26_settings(copier_yml: dict[str, Any]) -> None:
    assert copier_yml["_min_copier_version"] == "9.18.2"
    assert copier_yml["_subdirectory"] == "template"
    assert copier_yml["_answers_file"] == ".copier-answers.yml"
    assert copier_yml["_templates_suffix"] == ".jinja"


@pytest.mark.parametrize(
    "key", ["_tasks", "_migrations", "_jinja_extensions", "_message_after_copy"]
)
def test_c26_banned_settings(copier_yml: dict[str, Any], key: str) -> None:
    assert key not in copier_yml


def test_c26_no_copier_conf_src_path() -> None:
    files = [COPIER_YML, *(p for p in (TEMPLATE / "template").rglob("*") if p.is_file())]
    for p in files:
        assert "_copier_conf.src_path" not in p.read_text(encoding="utf-8"), p


def test_c26_skip_if_exists(copier_yml: dict[str, Any]) -> None:
    assert sorted(copier_yml["_skip_if_exists"]) == sorted(
        [
            "docs/adr/*.md",
            "docs/runbooks/*.md",
            "kuan-workbench/**",
            ".kuanflow/templates/**",
            ".kuanflow/config.local.yaml",
            "orca.yaml",
        ]
    )


def test_c26_question_set(copier_yml: dict[str, Any]) -> None:
    assert {k for k in copier_yml if not k.startswith("_")} == QUESTIONS


def test_c26_question_types_and_defaults(copier_yml: dict[str, Any]) -> None:
    q = copier_yml
    assert q["project_name"]["type"] == "str"
    assert q["stack"]["type"] == "str"
    assert sorted(_choices(q["stack"])) == sorted(STACKS)
    assert q["stack"]["default"] == "java-maven"
    assert q["ticket_pattern"]["default"] == "[A-Z][A-Z0-9]+-[0-9]+"
    assert q["fintech"]["type"] == "bool"
    assert q["fintech"]["default"] is True
    assert q["protected_paths"]["type"] == "yaml"
    assert _default(q["protected_paths"]) == [
        "src/main/resources/db/migration/**",
        "**/legacy/**",
    ]
    assert q["services"]["type"] == "yaml"
    assert _default(q["services"]) == []
    assert sorted(_choices(q["artifacts_commit"])) == ["full", "minimal", "none"]
    assert q["artifacts_commit"]["default"] == "minimal"
    assert q["use_orca"]["type"] == "bool"
    assert q["use_orca"]["default"] is True
    for key in ["knowledge_repo", "jira_project_key", "kuanflow_version"]:
        assert q[key]["type"] == "str", key
        assert q[key]["default"] == "", key


# --- C25 result: answers file -----------------------------------------------------------------


@pytest.mark.parametrize("stack", STACKS)
def test_c25_answers_file(rendered: dict[str, Path], stack: str) -> None:
    ans = answers_file(rendered[stack])
    assert ans["_src_path"] == CACHE
    assert ans["_commit"] == f"v{current_version()}"
    assert QUESTIONS <= set(ans), QUESTIONS - set(ans)
    assert ans["kuanflow_version"] == current_version()
    for key, value in load_answers(stack).items():
        assert ans[key] == value, key


@pytest.mark.parametrize("stack", STACKS)
def test_c26_stack_default_answers(rendered: dict[str, Path], stack: str) -> None:
    ans = answers_file(rendered[stack])
    for key, value in STACK_DEFAULTS[stack].items():
        assert ans[f"{key}_cmd"] == value, key


# --- C27 rendered tree ------------------------------------------------------------------------


@pytest.mark.parametrize("stack", STACKS)
def test_c27_tree_is_exact(rendered: dict[str, Path], stack: str) -> None:
    use_orca = load_answers(stack).get("use_orca", True)
    expected = BASE_TREE | ({"orca.yaml"} if use_orca else set())
    assert tree(rendered[stack]) == expected


def test_c27_orca_off_has_no_orca_file(rendered: dict[str, Path]) -> None:
    assert not (rendered["other"] / "orca.yaml").exists()


@pytest.mark.parametrize("stack", ["java-maven", "python"])
def test_c27_orca_content(rendered: dict[str, Path], stack: str) -> None:
    text = (rendered[stack] / "orca.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(text) == {"worktree": {"sharedDirectories": []}}
    assert "#" in text, "orca.yaml keeps the PKG §18.9 comment"
    assert is_english(text)


@pytest.mark.parametrize("stack", STACKS)
@pytest.mark.parametrize("script", SCRIPTS)
def test_c27_scripts_identical_and_executable(
    rendered: dict[str, Path], stack: str, script: str
) -> None:
    got = rendered[stack] / ".kuanflow" / "scripts" / script
    assert got.read_bytes() == (PLUGIN_SCRIPTS / script).read_bytes()
    mode = got.stat().st_mode
    assert mode & stat.S_IXUSR, oct(mode)
    assert os.access(got, os.X_OK)


def test_c27_scripts_not_kept_in_templates() -> None:
    assert not (TEMPLATE / "template" / ".kuanflow" / "scripts").exists()


def test_c27_no_jinja_or_copier_files(rendered: dict[str, Path]) -> None:
    for stack in STACKS:
        for rel in tree(rendered[stack]):
            assert not rel.endswith(".jinja"), rel
            assert Path(rel).name not in {"copier.yml", "copier.yaml"}, rel


@pytest.mark.parametrize(
    "rel", ["AGENTS.md", "CLAUDE.md", ".gitignore", ".worktreeinclude", ".github"]
)
def test_c27_patcher_targets_not_rendered(rendered: dict[str, Path], rel: str) -> None:
    for stack in STACKS:
        assert not (rendered[stack] / rel).exists(), (stack, rel)


def test_c27_kuanflow_readme(rendered: dict[str, Path]) -> None:
    text = (rendered["java-maven"] / ".kuanflow" / "README.md").read_text(encoding="utf-8")
    for needle in [
        "config.yaml",
        "config.local.yaml",
        "scripts/",
        "templates/",
        "manifest.json",
        "kuanflow upgrade",
        "kuanflow doctor",
    ]:
        assert needle in text, needle
    lines = [ln for ln in text.splitlines() if ".copier-answers.yml" in ln]
    assert lines, "README must name .copier-answers.yml"
    pattern = re.compile(
        r"\b(do not|don't|never|must not|not)\b.{0,60}\b(edit|modify|change)", re.I
    )
    assert any(pattern.search(ln) for ln in lines), lines
    assert is_english(text)


def test_c27_adr_template(rendered: dict[str, Path]) -> None:
    text = (rendered["java-maven"] / "docs" / "adr" / "0000-template.md").read_text(
        encoding="utf-8"
    )
    fm = frontmatter(text)
    assert {"id", "title", "status", "date", "deciders"} <= set(fm), fm
    sections = [ln for ln in text.splitlines() if ln.startswith("## ")]
    assert len(sections) == 5, sections
    assert is_english(text)


# --- C28 .kuanflow/config.yaml ----------------------------------------------------------------


def expected_config(answers: dict[str, Any]) -> dict[str, Any]:
    stack = answers["stack"]
    return {
        "schema_version": 1,
        "kuanflow": {"min_version": current_version()},
        "project": {"name": answers["project_name"], "stack": stack},
        "commands": dict(STACK_DEFAULTS[stack]),
        "paths": {
            "work": "kuan-workbench/work",
            "wiki": "kuan-workbench/wiki",
            "scratch": ".kuanflow/scratch",
            "adr": "docs/adr",
            "runbooks": "docs/runbooks",
        },
        "artifacts": {"commit": answers.get("artifacts_commit", "minimal")},
        "work": {"ticket_pattern": "[A-Z][A-Z0-9]+-[0-9]+"},
        "protected_paths": ["src/main/resources/db/migration/**", "**/legacy/**"],
        "risk": {"fintech": answers.get("fintech", True)},
        "workflows": {"enabled": [f"w{i}" for i in range(11)]},
        "debug": {
            "services": answers.get("services", []),
            "budget": {
                "max_turns_total": 80,
                "classification": 5,
                "subagent": 20,
                "fix_rounds": 3,
            },
            "allow_prod_log_access": False,
        },
        "knowledge": {"repo": ""},
        "integrations": {"jira_project_key": ""},
        "guard": {"extra_block_patterns": []},
    }


@pytest.mark.parametrize("stack", STACKS)
def test_c28_config_content(rendered: dict[str, Path], stack: str) -> None:
    assert config(rendered[stack]) == expected_config(load_answers(stack))


def test_c28_yaml_special_name_round_trips(rendered: dict[str, Path]) -> None:
    assert config(rendered["python"])["project"]["name"] == "py-svc: β #1"
    assert answers_file(rendered["python"])["project_name"] == "py-svc: β #1"


def test_c28_yaml_special_values_round_trip(tmp_path: Path) -> None:
    data = {
        "project_name": "x: \"y\" 'z' #1",
        "stack": "node",
        "build_cmd": "make build ARGS='-a: b' # not a comment",
        "test_cmd": '"quoted" test',
        "verify_cmd": "- verify: [x]",
        "ticket_pattern": "'[A-Z]+'-#\\d+",
        "knowledge_repo": "https://git.example/{org}/k?x=1&y=*",
        "jira_project_key": "@ORD",
        "protected_paths": ["a: b/**", "#x/**"],
        "services": ["svc: one", "*two"],
    }
    engine().render(tmp_path / "p", data)
    cfg = config(tmp_path / "p")
    assert cfg["project"]["name"] == data["project_name"]
    assert cfg["commands"]["build"] == data["build_cmd"]
    assert cfg["commands"]["test"] == data["test_cmd"]
    assert cfg["commands"]["verify"] == data["verify_cmd"]
    assert cfg["work"]["ticket_pattern"] == data["ticket_pattern"]
    assert cfg["knowledge"]["repo"] == data["knowledge_repo"]
    assert cfg["integrations"]["jira_project_key"] == data["jira_project_key"]
    assert cfg["protected_paths"] == data["protected_paths"]
    assert cfg["debug"]["services"] == data["services"]


_TOP = re.compile(r"^[A-Za-z_][\w-]*:")
_CHILD = re.compile(r"^\s+[A-Za-z_][\w-]*:")


def _blank_between(lines: list[str], i: int, j: int) -> bool:
    return any(not lines[k].strip() for k in range(i + 1, j))


@pytest.mark.parametrize("stack", STACKS)
def test_c28_blank_line_between_top_level_sections(rendered: dict[str, Path], stack: str) -> None:
    lines = (rendered[stack] / ".kuanflow" / "config.yaml").read_text(encoding="utf-8").splitlines()
    tops = [i for i, ln in enumerate(lines) if _TOP.match(ln)]
    assert len(tops) == 14, [lines[i] for i in tops]
    for a, b in zip(tops, tops[1:], strict=False):
        assert _blank_between(lines, a, b), (lines[a], lines[b])


@pytest.mark.parametrize("stack", STACKS)
@pytest.mark.parametrize("section", ["commands", "paths"])
def test_c28_blank_line_between_keys(rendered: dict[str, Path], stack: str, section: str) -> None:
    lines = (rendered[stack] / ".kuanflow" / "config.yaml").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{section}:")
    end = next((i for i in range(start + 1, len(lines)) if _TOP.match(lines[i])), len(lines))
    keys = [i for i in range(start + 1, end) if _CHILD.match(lines[i])]
    assert len(keys) == 5, lines[start:end]
    for a, b in zip(keys, keys[1:], strict=False):
        assert _blank_between(lines, a, b), (lines[a], lines[b])


@pytest.mark.parametrize("stack", STACKS)
def test_c28_config_validates_against_schema(rendered: dict[str, Path], stack: str) -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(config(rendered[stack])))
    assert not errors, [e.message for e in errors]
