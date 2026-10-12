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


# Every str answer and where it lands in config.yaml.
STR_ANSWERS: dict[str, tuple[str, ...]] = {
    "project_name": ("project", "name"),
    "build_cmd": ("commands", "build"),
    "test_cmd": ("commands", "test"),
    "verify_cmd": ("commands", "verify"),
    "single_test_cmd": ("commands", "single_test"),
    "lint_cmd": ("commands", "lint"),
    "ticket_pattern": ("work", "ticket_pattern"),
    "knowledge_repo": ("knowledge", "repo"),
    "jira_project_key": ("integrations", "jira_project_key"),
    "kuanflow_version": ("kuanflow", "min_version"),
}
HOSTILE = {
    "quotes": "a\"b'c\\d: #e",
    "newline": "line one: x\n  - two # y\n'three\"",
    "jinja": "{{ 7*7 }} {% raw %}x{% endraw %} {# c #}",
    "unicode": "Dịch vụ β \u2028 \u2029 \u0085 \x01 \x7f end",
}


def _dig(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    for key in path:
        data = data[key]
    return data


@pytest.mark.parametrize("kind", list(HOSTILE))
def test_c28b_every_string_answer_round_trips(tmp_path: Path, kind: str) -> None:
    value = HOSTILE[kind]
    data: dict[str, Any] = {key: f"{value} [{key}]" for key in STR_ANSWERS}
    data["stack"] = "node"
    data["protected_paths"] = [value, f"{value}/**"]
    data["services"] = [value, f"svc {value}"]
    dst = tmp_path / "p"
    engine().render(dst, data)
    cfg = config(dst)
    ans = answers_file(dst)
    for key, path in STR_ANSWERS.items():
        assert _dig(cfg, path) == data[key], key
        assert ans[key] == data[key], key
    assert cfg["protected_paths"] == data["protected_paths"]
    assert cfg["debug"]["services"] == data["services"]
    assert ans["protected_paths"] == data["protected_paths"]
    assert ans["services"] == data["services"]
    # nothing else changed: same keys as a plain render
    assert set(cfg) == set(expected_config({"project_name": "x", "stack": "node"}))


def test_c28b_non_ascii_written_literally(rendered: dict[str, Path]) -> None:
    text = (rendered["python"] / ".kuanflow" / "config.yaml").read_text(encoding="utf-8")
    assert "py-svc: β #1" in text, text
    assert "\\u03b2" not in text.lower(), text


def test_c28b_line_breaks_and_controls_stay_escaped(tmp_path: Path) -> None:
    name = "Dịch vụ β\u2028x\u2029y\u0085z\x01\x1b\x7f\tq\rr\nend"
    dst = tmp_path / "p"
    engine().render(dst, {"project_name": name, "stack": "python"})
    text = (dst / ".kuanflow" / "config.yaml").read_text(encoding="utf-8")
    assert "Dịch vụ β" in text, "non-ASCII letters are written literally"
    for ch in ["\u2028", "\u2029", "\u0085", "\x01", "\x1b", "\x7f", "\t", "\r"]:
        assert ch not in text, repr(ch)
    name_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("name:")]
    assert len(name_lines) == 1, name_lines
    assert config(dst)["project"]["name"] == name
    assert answers_file(dst)["project_name"] == name


# --- C26a list answers validated --------------------------------------------------------------


@pytest.mark.parametrize("key", ["protected_paths", "services"])
@pytest.mark.parametrize(
    "bad",
    ["src/**", {"a": 1}, [1], ["ok", None], ["ok", ["nested"]], 7],
    ids=["string", "mapping", "int-item", "null-item", "list-item", "int"],
)
def test_c26a_list_answers_validated(tmp_path: Path, key: str, bad: Any) -> None:
    dst = tmp_path / "p"
    with pytest.raises(ValueError):
        engine().render(dst, {"project_name": "x", "stack": "python", key: bad})
    assert not (dst / ".kuanflow" / "config.yaml").exists()
    assert tree(dst) == set(), tree(dst)


@pytest.mark.parametrize("key", ["protected_paths", "services"])
@pytest.mark.parametrize("good", [[], ["a"], ["src/**", "**/legacy/**"]])
def test_c26a_list_answers_accepted(tmp_path: Path, key: str, good: list[str]) -> None:
    dst = tmp_path / "p"
    engine().render(dst, {"project_name": "x", "stack": "python", key: good})
    cfg = config(dst)
    got = cfg["protected_paths"] if key == "protected_paths" else cfg["debug"]["services"]
    assert got == good


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


# --- C28a merge-friendly debug section + real 3-way update ---------------------------------------


def _section(lines: list[str], name: str) -> tuple[int, int]:
    start = lines.index(f"{name}:")
    end = next((i for i in range(start + 1, len(lines)) if _TOP.match(lines[i])), len(lines))
    return start, end


_DEBUG_KEY = re.compile(r"^  [A-Za-z_][\w-]*:")
_BUDGET_KEY = re.compile(r"^    [A-Za-z_][\w-]*:")


@pytest.mark.parametrize("stack", STACKS)
def test_c28a_debug_layout(rendered: dict[str, Path], stack: str) -> None:
    lines = (rendered[stack] / ".kuanflow" / "config.yaml").read_text(encoding="utf-8").splitlines()
    start, end = _section(lines, "debug")
    keys = [i for i in range(start + 1, end) if _DEBUG_KEY.match(lines[i])]
    assert [lines[i].split(":")[0].strip() for i in keys] == [
        "services",
        "budget",
        "allow_prod_log_access",
    ], lines[start:end]
    for a, b in zip(keys, keys[1:], strict=False):
        assert _blank_between(lines, a, b), (lines[a], lines[b])
    b_start = keys[1]
    assert lines[b_start].split("#")[0].rstrip() == "  budget:", "budget must be a block mapping"
    b_keys = [i for i in range(b_start + 1, keys[2]) if _BUDGET_KEY.match(lines[i])]
    assert [lines[i].split(":")[0].strip() for i in b_keys] == [
        "max_turns_total",
        "classification",
        "subagent",
        "fix_rounds",
    ], lines[b_start : keys[2]]
    for a, b in zip(b_keys, b_keys[1:], strict=False):
        assert _blank_between(lines, a, b), (lines[a], lines[b])


V1, V2 = "0.90.0", "0.91.0"
GIT_ID = ["-c", "user.name=Kuanflow Test", "-c", "user.email=test@example.com"]
UPSTREAM_MARK = "# upstream v2 note"


def _run_git(repo: Path, *args: str) -> str:
    import subprocess

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    proc = subprocess.run(
        ["git", "-C", str(repo), *GIT_ID, *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=60,
    )
    return proc.stdout


def _copy_content(dst: Path) -> Path:
    import shutil

    dst.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "VERSION", dst / "VERSION")
    shutil.copytree(TEMPLATE, dst / "templates" / "project")
    shutil.copytree(PLUGIN_SCRIPTS, dst / "plugins" / "kuanflow" / "scripts")
    return dst


def _leaf_line(lines: list[str], section: str, leaf: str) -> int:
    """Index of the line holding ``leaf`` (dotted below ``section``) in config text."""
    start, end = _section(lines, section)
    key = leaf.split(".")[-1]
    pat = re.compile(rf"^\s+{re.escape(key)}:")
    hits = [i for i in range(start + 1, end) if pat.match(lines[i])]
    assert len(hits) == 1, (section, leaf, lines[start:end])
    return hits[0]


_BUDGET_VALUE = re.compile(r"\b(max_turns_total|classification|subagent|fix_rounds): (\d+)")


def _upstream_edit(jinja: str, section: str, leaf: str) -> str:
    """The v2 template change: one leaf of the config template, nothing else."""
    if leaf.startswith("budget."):
        key = leaf.split(".")[1]
        out, n = re.subn(rf"\b{key}: (\d+)", lambda m: f"{key}: {int(m.group(1)) + 100}", jinja)
        assert n == 1, (leaf, n)
        return out
    lines = jinja.split("\n")
    i = _leaf_line(lines, section, leaf)
    lines[i] = f"{lines[i]}  {UPSTREAM_MARK}"
    return "\n".join(lines)


def _local_edit(text: str, section: str, leaf: str) -> str:
    """The user's change in the rendered config.yaml: one leaf, nothing else."""
    if leaf.startswith("budget."):
        key = leaf.split(".")[1]
        out, n = re.subn(rf"\b{key}: (\d+)", lambda m: f"{key}: {int(m.group(1)) + 1}", text)
        assert n == 1, (leaf, n)
        return out
    lines = text.split("\n")
    i = _leaf_line(lines, section, leaf)
    if leaf == "services":
        j = i + 1
        while j < len(lines) and lines[j].lstrip().startswith("- "):
            j += 1
        assert j > i + 1, "fixture must render services as a block list"
        lines.insert(j, '    - "svc-local"')
    elif leaf == "allow_prod_log_access":
        lines[i] = lines[i].replace("false", "true", 1)
    else:
        indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
        lines[i] = f'{indent}{leaf}: "local-{leaf}"'
    return "\n".join(lines)


def _expected_local(cfg: dict[str, Any], section: str, leaf: str, before: dict[str, Any]) -> None:
    sec = cfg[section]
    if leaf.startswith("budget."):
        key = leaf.split(".")[1]
        assert sec["budget"][key] == before[section]["budget"][key] + 1, sec
    elif leaf == "services":
        assert sec["services"] == [*before[section]["services"], "svc-local"], sec
    elif leaf == "allow_prod_log_access":
        assert sec["allow_prod_log_access"] is True, sec
    else:
        assert sec[leaf] == f"local-{leaf}", sec


def _expected_upstream(
    text: str, cfg: dict[str, Any], section: str, leaf: str, before: dict[str, Any]
) -> None:
    if leaf.startswith("budget."):
        key = leaf.split(".")[1]
        assert cfg[section]["budget"][key] == before[section]["budget"][key] + 100, cfg[section]
        return
    lines = text.split("\n")
    assert UPSTREAM_MARK in lines[_leaf_line(lines, section, leaf)], text


_COMMANDS = ["build", "test", "verify", "single_test", "lint"]
_PATHS = ["work", "wiki", "scratch", "adr", "runbooks"]
_DEBUG = [
    "services",
    "budget.max_turns_total",
    "budget.classification",
    "budget.subagent",
    "budget.fix_rounds",
    "allow_prod_log_access",
]


def _adjacent_pairs(section: str, leaves: list[str]) -> list[tuple[str, str, str]]:
    out = []
    for a, b in zip(leaves, leaves[1:], strict=False):
        out += [(section, a, b), (section, b, a)]
    return out


_MERGE_CASES = [
    *_adjacent_pairs("commands", _COMMANDS),
    *_adjacent_pairs("paths", _PATHS),
    *_adjacent_pairs("debug", _DEBUG),
    ("debug", "services", "allow_prod_log_access"),
    ("debug", "allow_prod_log_access", "services"),
]


@pytest.fixture(scope="module")
def content_v1(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _copy_content(tmp_path_factory.mktemp("content-v1") / "c")


@pytest.mark.parametrize(
    ("section", "local", "upstream"),
    _MERGE_CASES,
    ids=[f"{s}:{loc}-vs-{up}" for s, loc, up in _MERGE_CASES],
)
def test_c28a_three_way_update_merges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content_v1: Path,
    section: str,
    local: str,
    upstream: str,
) -> None:
    import copier

    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ["AUTHOR", "COMMITTER"]:
        monkeypatch.setenv(f"GIT_{var}_NAME", "Kuanflow Test")
        monkeypatch.setenv(f"GIT_{var}_EMAIL", "test@example.com")

    content_v2 = _copy_content(tmp_path / "content-v2")
    jinja = content_v2 / "templates/project/template/.kuanflow/config.yaml.jinja"
    jinja.write_text(
        _upstream_edit(jinja.read_text(encoding="utf-8"), section, upstream), encoding="utf-8"
    )

    proj = tmp_path / "proj"
    proj.mkdir()
    _run_git(proj, "init", "-q", "-b", "main")
    (proj / ".gitignore").write_text(".kuanflow/cache/\n", encoding="utf-8")
    answers = {"project_name": "merge-svc", "stack": "python", "services": ["svc-a", "svc-b"]}
    engine().render(proj, answers, version=V1, content=content_v1)
    _run_git(proj, "add", "-A")
    _run_git(proj, "commit", "-q", "-m", "render v1")

    cfg_path = proj / ".kuanflow" / "config.yaml"
    before = config(proj)
    cfg_path.write_text(
        _local_edit(cfg_path.read_text(encoding="utf-8"), section, local), encoding="utf-8"
    )
    _expected_local(config(proj), section, local, before)
    _run_git(proj, "commit", "-q", "-am", "local edit")

    engine().assemble_template(proj / CACHE, [(V1, content_v1), (V2, content_v2)])
    monkeypatch.chdir(proj)
    copier.run_update(
        ".",
        vcs_ref=f"v{V2}",
        defaults=True,
        overwrite=True,
        conflict="inline",
        quiet=True,
    )

    assert _run_git(proj, "ls-files", "-u") == "", _run_git(proj, "status", "--porcelain")
    text = cfg_path.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text and ">>>>>>>" not in text, text
    after = config(proj)
    _expected_local(after, section, local, before)
    _expected_upstream(text, after, section, upstream, before)
    assert answers_file(proj)["_commit"] == f"v{V2}"


# --- C28c blank line between project.name and project.stack (fix round 2) ----------------------


@pytest.mark.parametrize("stack", STACKS)
def test_c28c_blank_line_between_project_keys(rendered: dict[str, Path], stack: str) -> None:
    lines = (rendered[stack] / ".kuanflow" / "config.yaml").read_text(encoding="utf-8").splitlines()
    start, end = _section(lines, "project")
    keys = [i for i in range(start + 1, end) if _CHILD.match(lines[i])]
    assert [lines[i].split(":")[0].strip() for i in keys] == ["name", "stack"], lines[start:end]
    assert _blank_between(lines, keys[0], keys[1]), lines[start:end]


_PROJECT_CASES = [("project", "name", "stack"), ("project", "stack", "name")]


@pytest.mark.parametrize(
    ("section", "local", "upstream"),
    _PROJECT_CASES,
    ids=[f"{s}:{loc}-vs-{up}" for s, loc, up in _PROJECT_CASES],
)
def test_c28c_three_way_update_merges_project_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content_v1: Path,
    section: str,
    local: str,
    upstream: str,
) -> None:
    # Same real Copier 3-way update as C28a, for the leaf pair (project.name, project.stack).
    test_c28a_three_way_update_merges(tmp_path, monkeypatch, content_v1, section, local, upstream)


# --- C28d invisible/format characters stay escaped (fix round 2) -------------------------------


def _chars(*ranges: tuple[int, int]) -> str:
    return "".join(chr(c) for lo, hi in ranges for c in range(lo, hi + 1))


ESCAPED_CHARS: dict[str, str] = {
    "soft-hyphen": _chars((0x00AD, 0x00AD)),
    "arabic-letter-mark": _chars((0x061C, 0x061C)),
    "mongolian-vowel-sep": _chars((0x180E, 0x180E)),
    "zw-and-marks": _chars((0x200B, 0x200F)),
    "bidi-embeddings": _chars((0x202A, 0x202E)),
    "word-joiner-invisibles": _chars((0x2060, 0x2064)),
    "bidi-isolates-deprecated": _chars((0x2066, 0x206F)),
    "bom": _chars((0xFEFF, 0xFEFF)),
    "interlinear": _chars((0xFFF9, 0xFFFB)),
    "noncharacters": _chars((0xFFFE, 0xFFFF)),
    "tag-language": _chars((0xE0001, 0xE0001)),
    "tags": _chars((0xE0020, 0xE007F)),
}


def _hostile_answers(value: str) -> dict[str, Any]:
    return {
        "project_name": f"name{value}end",
        "stack": "node",
        "build_cmd": f"make{value} build",
        "ticket_pattern": f"[A-Z]+{value}-\\d+",
        "knowledge_repo": f"https://k.example/{value}",
        "jira_project_key": f"ORD{value}",
        "protected_paths": [f"src{value}/**"],
        "services": [f"svc{value}"],
    }


def _check_round_trip(cfg: dict[str, Any], data: dict[str, Any]) -> None:
    assert cfg["project"]["name"] == data["project_name"]
    assert cfg["commands"]["build"] == data["build_cmd"]
    assert cfg["work"]["ticket_pattern"] == data["ticket_pattern"]
    assert cfg["knowledge"]["repo"] == data["knowledge_repo"]
    assert cfg["integrations"]["jira_project_key"] == data["jira_project_key"]
    assert cfg["protected_paths"] == data["protected_paths"]
    assert cfg["debug"]["services"] == data["services"]


@pytest.mark.parametrize("group", list(ESCAPED_CHARS))
def test_c28d_format_chars_escaped_and_round_trip(tmp_path: Path, group: str) -> None:
    chars = ESCAPED_CHARS[group]
    data = _hostile_answers(chars)
    dst = tmp_path / "p"
    engine().render(dst, data)
    raw = (dst / ".kuanflow" / "config.yaml").read_bytes()
    text = raw.decode("utf-8")
    present = [f"U+{ord(c):04X}" for c in chars if c in text]
    assert not present, f"written raw: {present}"
    for c in chars:
        assert c.encode("utf-8") not in raw, f"U+{ord(c):04X}"
    _check_round_trip(config(dst), data)


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff", "\udc00"])
def test_c28d_lone_surrogate_round_trips_or_raises(tmp_path: Path, surrogate: str) -> None:
    data = _hostile_answers(surrogate)
    dst = tmp_path / "p"
    cfg_path = dst / ".kuanflow" / "config.yaml"
    try:
        engine().render(dst, data)
    except Exception:  # noqa: BLE001 - either outcome is allowed; a broken file is not
        if cfg_path.exists():
            _check_round_trip(config(dst), data)
        return
    raw = cfg_path.read_bytes()
    text = raw.decode("utf-8")  # strict: no lone surrogate (or its CESU bytes) in the file
    assert surrogate not in text
    _check_round_trip(config(dst), data)


# --- C28e literal non-ASCII for every string answer (fix round 2) ------------------------------

_NON_ASCII = "Dịch vụ β đơn hàng 注文 😀"


def test_c28e_non_ascii_literal_in_every_string_field(tmp_path: Path) -> None:
    data: dict[str, Any] = {
        key: f"{_NON_ASCII} [{key}]"
        for key in [
            "project_name",
            "build_cmd",
            "test_cmd",
            "verify_cmd",
            "single_test_cmd",
            "lint_cmd",
            "ticket_pattern",
            "knowledge_repo",
            "jira_project_key",
        ]
    }
    data["stack"] = "node"
    data["protected_paths"] = [f"{_NON_ASCII} [pp1]/**", f"{_NON_ASCII} [pp2]"]
    data["services"] = [f"{_NON_ASCII} [svc1]", f"{_NON_ASCII} [svc2]"]
    dst = tmp_path / "p"
    engine().render(dst, data)
    text = (dst / ".kuanflow" / "config.yaml").read_text(encoding="utf-8")
    expected = [v for k, v in data.items() if k not in ("stack", "protected_paths", "services")]
    expected += data["protected_paths"] + data["services"]
    for value in expected:
        assert value in text, f"not written literally: {value!r}"
    assert "\\u" not in text.lower(), "no \\u escapes for ordinary non-ASCII"
    cfg = config(dst)
    _check_round_trip(cfg, data)
    assert cfg["commands"] == {
        "build": data["build_cmd"],
        "test": data["test_cmd"],
        "verify": data["verify_cmd"],
        "single_test": data["single_test_cmd"],
        "lint": data["lint_cmd"],
    }
