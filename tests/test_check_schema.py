"""Contract tests C35 (tests/check_schema.py) and C29 (config.schema.json rules)."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tests" / "check_schema.py"
SCHEMA = REPO_ROOT / "templates" / "project" / "schema" / "config.schema.json"

# --- C35 the checker --------------------------------------------------------------------------


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        cwd=REPO_ROOT,
    )


def load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kf_test_check_schema_mod", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_c35_clean_repo_exits_0() -> None:
    proc = run()
    assert proc.returncode == 0, proc.stderr


def test_c35_arguments_rejected() -> None:
    assert run("extra").returncode == 2


def test_c35_invalid_schema_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    checker = load_checker()
    bad = tmp_path / "config.schema.json"
    bad.write_text(json.dumps({"type": "no-such-type"}), encoding="utf-8")
    monkeypatch.setattr(checker, "SCHEMA", bad)
    assert checker.main([]) == 1
    lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    assert lines[0].startswith(f"{bad}: "), lines


def test_c35_config_errors_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    checker = load_checker()
    strict = tmp_path / "config.schema.json"
    strict.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["must_exist_a", "must_exist_b"],
            }
        ),
        encoding="utf-8",
    )
    answers = tmp_path / "answers"
    answers.mkdir()
    (answers / "one.yml").write_text("project_name: one\nstack: node\n", encoding="utf-8")
    monkeypatch.setattr(checker, "SCHEMA", strict)
    monkeypatch.setattr(checker, "ANSWERS_DIR", answers)
    assert checker.main([]) == 1
    lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.strip()]
    assert len(lines) == 2, lines
    for ln in lines:
        name, path, message = ln.split(": ", 2)
        assert name.endswith("one.yml"), ln
        assert path == "$", ln
        assert "must_exist_" in message, ln


# --- C36 answers fixtures ---------------------------------------------------------------------

ANSWERS_DIR = REPO_ROOT / "tests" / "answers"


def test_c36_answers_fixtures() -> None:
    import yaml

    stacks = ["java-maven", "java-gradle", "node", "python", "other"]
    assert sorted(p.name for p in ANSWERS_DIR.glob("*.yml")) == sorted(f"{s}.yml" for s in stacks)
    for stack in stacks:
        data = yaml.safe_load((ANSWERS_DIR / f"{stack}.yml").read_text(encoding="utf-8"))
        assert data["stack"] == stack
        assert isinstance(data["project_name"], str) and data["project_name"]
        assert "kuanflow_version" not in data
        extra = {k: v for k, v in data.items() if k not in {"project_name", "stack"}}
        if stack == "other":
            assert extra == {
                "use_orca": False,
                "fintech": False,
                "artifacts_commit": "none",
                "services": ["a-svc", "b-svc"],
            }
        else:
            assert extra == {}, stack
        if stack == "python":
            assert data["project_name"] == "py-svc: β #1"


# --- C29 schema rules -------------------------------------------------------------------------


def base_config() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kuanflow": {"min_version": "0.3.0"},
        "project": {"name": "order-service", "stack": "java-maven"},
        "commands": {
            "build": "./mvnw -q -DskipTests package",
            "test": "./mvnw -q test",
            "verify": "./mvnw -q verify",
            "single_test": "./mvnw -q -Dtest={test} test",
            "lint": "./mvnw -q spotless:check",
        },
        "paths": {
            "work": "kuan-workbench/work",
            "wiki": "kuan-workbench/wiki",
            "scratch": ".kuanflow/scratch",
            "adr": "docs/adr",
            "runbooks": "docs/runbooks",
        },
        "artifacts": {"commit": "minimal"},
        "work": {"ticket_pattern": "[A-Z][A-Z0-9]+-[0-9]+"},
        "protected_paths": ["src/main/resources/db/migration/**", "**/legacy/**"],
        "risk": {"fintech": True},
        "workflows": {"enabled": [f"w{i}" for i in range(11)]},
        "debug": {
            "services": ["order-service"],
            "budget": {"max_turns_total": 80, "classification": 5, "subagent": 20, "fix_rounds": 3},
            "allow_prod_log_access": False,
        },
        "knowledge": {"repo": ""},
        "integrations": {"jira_project_key": ""},
        "guard": {"extra_block_patterns": []},
    }


def minimal_config() -> dict[str, Any]:
    cfg = base_config()
    for key in ["work", "debug", "knowledge", "integrations", "guard"]:
        del cfg[key]
    del cfg["commands"]["single_test"]
    del cfg["commands"]["lint"]
    return cfg


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def with_value(cfg: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    cfg = copy.deepcopy(cfg)
    *parents, last = dotted.split(".")
    node = cfg
    for p in parents:
        node = node.setdefault(p, {})
    node[last] = value
    return cfg


def without(cfg: dict[str, Any], dotted: str) -> dict[str, Any]:
    cfg = copy.deepcopy(cfg)
    *parents, last = dotted.split(".")
    node = cfg
    for p in parents:
        node = node[p]
    del node[last]
    return cfg


def valid(v: Draft202012Validator, cfg: dict[str, Any]) -> bool:
    return not list(v.iter_errors(cfg))


def test_c29_schema_is_draft_2020_12() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_c29_base_config_valid(validator: Draft202012Validator) -> None:
    errors = [e.message for e in validator.iter_errors(base_config())]
    assert not errors, errors


def test_c29_minimal_config_valid(validator: Draft202012Validator) -> None:
    errors = [e.message for e in validator.iter_errors(minimal_config())]
    assert not errors, errors


REQUIRED = [
    "schema_version",
    "kuanflow",
    "kuanflow.min_version",
    "project",
    "project.name",
    "project.stack",
    "commands",
    "commands.build",
    "commands.test",
    "commands.verify",
    "paths",
    "paths.work",
    "paths.wiki",
    "paths.scratch",
    "paths.adr",
    "paths.runbooks",
    "artifacts",
    "artifacts.commit",
    "protected_paths",
    "risk",
    "risk.fintech",
    "workflows",
    "workflows.enabled",
]


@pytest.mark.parametrize("key", REQUIRED)
def test_c29_required(validator: Draft202012Validator, key: str) -> None:
    assert not valid(validator, without(base_config(), key))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 2),
        ("schema_version", "1"),
        ("schema_version", 0),
        ("kuanflow.min_version", "1.4"),
        ("kuanflow.min_version", "v1.4.0"),
        ("kuanflow.min_version", "01.4.0"),
        ("kuanflow.min_version", 140),
        ("kuanflow.min_version", ""),
        ("commands.build", ""),
        ("commands.test", ""),
        ("commands.verify", ""),
        ("commands.build", 5),
        ("commands.verify", None),
        ("artifacts.commit", "partial"),
        ("artifacts.commit", ""),
        ("protected_paths", "src/**"),
        ("protected_paths", [1]),
        ("risk.fintech", "yes"),
        ("risk.fintech", 1),
        ("workflows.enabled", ["w11"]),
        ("workflows.enabled", ["w0", "w0"]),
        ("workflows.enabled", "w0"),
        ("commands.single_test", 5),
        ("commands.lint", 5),
        ("work.ticket_pattern", 5),
        ("knowledge.repo", 5),
        ("integrations.jira_project_key", 5),
        ("guard.extra_block_patterns", "rm -rf"),
        ("guard.extra_block_patterns", [1]),
        ("debug.services", "a-svc"),
        ("debug.budget.max_turns_total", "80"),
        ("debug.allow_prod_log_access", "no"),
    ],
)
def test_c29_invalid_values(validator: Draft202012Validator, key: str, value: Any) -> None:
    assert not valid(validator, with_value(base_config(), key, value))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("kuanflow.min_version", "1.4.0"),
        ("kuanflow.min_version", "0.3.0-dev"),
        ("kuanflow.min_version", "1.0.0-rc.1"),
        ("artifacts.commit", "full"),
        ("artifacts.commit", "none"),
        ("protected_paths", []),
        ("risk.fintech", False),
        ("workflows.enabled", ["w0", "w5", "w10"]),
        ("guard.extra_block_patterns", ["curl .*evil"]),
    ],
)
def test_c29_valid_values(validator: Draft202012Validator, key: str, value: Any) -> None:
    errors = [e.message for e in validator.iter_errors(with_value(base_config(), key, value))]
    assert not errors, errors


@pytest.mark.parametrize("section", ["project", "commands", "debug", "knowledge", "integrations"])
def test_c29_open_sections(validator: Draft202012Validator, section: str) -> None:
    cfg = with_value(base_config(), f"{section}.custom_key", "anything")
    errors = [e.message for e in validator.iter_errors(cfg)]
    assert not errors, errors


@pytest.mark.parametrize(
    "section",
    ["kuanflow", "paths", "artifacts", "work", "risk", "workflows", "guard", "debug.budget"],
)
def test_c29_closed_sections(validator: Draft202012Validator, section: str) -> None:
    assert not valid(validator, with_value(base_config(), f"{section}.custom_key", "x"))


@pytest.mark.parametrize("key", ["x-team", "x-", "x-custom_thing"])
def test_c29_top_level_x_extension_allowed(validator: Draft202012Validator, key: str) -> None:
    cfg = base_config()
    cfg[key] = {"anything": [1, 2]}
    errors = [e.message for e in validator.iter_errors(cfg)]
    assert not errors, errors


@pytest.mark.parametrize("key", ["extra", "X-team", "xteam", "x_team", "team-x-"])
def test_c29_top_level_other_rejected(validator: Draft202012Validator, key: str) -> None:
    cfg = base_config()
    cfg[key] = "v"
    assert not valid(validator, cfg)
