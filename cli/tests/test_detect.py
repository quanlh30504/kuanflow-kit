"""Contract tests C38 (detect) and C39 (collect_answers): kuanflow_cli.detect.

``shutil.which`` is always replaced through ``kuanflow_cli.detect.shutil.which`` so tools
installed on the test machine (claude, codex, orca, ...) never leak into results.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

LEGACY = "**/legacy/**"
MIGRATION = "src/main/resources/db/migration/**"


def detect_mod() -> ModuleType:
    return importlib.import_module("kuanflow_cli.detect")


def answers_error() -> type[Exception]:
    return importlib.import_module("kuanflow_cli.errors").AnswersError


def write(root: Path, rel: str, text: str = "") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def package_json(root: Path, scripts: dict[str, str] | None = None) -> None:
    data: dict[str, Any] = {"name": "web", "version": "1.0.0"}
    if scripts is not None:
        data["scripts"] = scripts
    write(root, "package.json", json.dumps(data, indent=2) + "\n")


@pytest.fixture
def which(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Install a fake ``which``; call the returned function with the tool names to "install"."""
    mod = detect_mod()
    installed: set[str] = set()

    def fake(name: str, *args: Any, **kwargs: Any) -> str | None:
        return f"/usr/bin/{name}" if name in installed else None

    monkeypatch.setattr(mod.shutil, "which", fake)

    def install(*names: str) -> None:
        installed.update(names)

    return install


@pytest.fixture
def root(tmp_path: Path, which: Callable[..., None]) -> Path:
    r = tmp_path / "my-svc"
    r.mkdir()
    return r


def answers(root: Path) -> dict[str, Any]:
    return detect_mod().detect(root).answers


def maven(x: str) -> dict[str, str]:
    return {
        "stack": "java-maven",
        "build_cmd": f"{x} -q -DskipTests package",
        "test_cmd": f"{x} -q test",
        "verify_cmd": f"{x} -q verify",
        "single_test_cmd": f"{x} -q -Dtest={{test}} test",
        "lint_cmd": f"{x} -q spotless:check",
    }


def gradle(x: str) -> dict[str, str]:
    return {
        "stack": "java-gradle",
        "build_cmd": f"{x} assemble",
        "test_cmd": f"{x} test",
        "verify_cmd": f"{x} check",
        "single_test_cmd": f"{x} test --tests {{test}}",
        "lint_cmd": f"{x} spotlessCheck",
    }


def base(name: str = "my-svc", protected: list[str] | None = None) -> dict[str, Any]:
    return {
        "project_name": name,
        "protected_paths": protected if protected is not None else [LEGACY],
        "use_orca": False,
    }


# --- C38 detect: shape -------------------------------------------------------------------------


def test_detection_is_frozen_dataclass(root: Path) -> None:
    det = detect_mod().detect(root)
    assert dataclasses.is_dataclass(det)
    assert isinstance(det.answers, dict)
    assert isinstance(det.agents, list)
    assert isinstance(det.notes, list)
    with pytest.raises(dataclasses.FrozenInstanceError):
        det.answers = {}  # type: ignore[misc]


def test_project_name_is_root_name(root: Path) -> None:
    assert answers(root)["project_name"] == "my-svc"


def test_other_stack_exact(root: Path) -> None:
    assert answers(root) == {**base(), "stack": "other"}


def test_never_runs_a_command(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("detect must not run commands")

    for name in ["run", "Popen", "call", "check_call", "check_output"]:
        monkeypatch.setattr(subprocess, name, boom)
    write(root, "pom.xml", "<project/>\n")
    package_json(root, {"test": "jest"})
    detect_mod().detect(root)


def test_reads_only_root(tmp_path: Path, which: Callable[..., None]) -> None:
    mono = tmp_path / "mono"
    write(mono, "pom.xml", "<project/>\n")
    write(mono, "mvnw", "#!/bin/sh\n")
    write(mono, "orca.yaml", "x: 1\n")
    (mono / ".claude").mkdir()
    (mono / "src/main/resources/db/migration").mkdir(parents=True)
    web = mono / "services" / "web"
    web.mkdir(parents=True)
    package_json(web, {"test": "vitest"})
    det = detect_mod().detect(web)
    assert det.answers == {
        **base("web"),
        "stack": "node",
        "test_cmd": "npm test",
        "single_test_cmd": "npm test -- {test}",
        "verify_cmd": "npm test",
    }
    assert det.agents == []


# --- C38 stack table ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "x"),
    [(["pom.xml"], "mvn"), (["mvnw"], "./mvnw"), (["pom.xml", "mvnw"], "./mvnw")],
    ids=["pom-no-wrapper", "wrapper-only", "pom-and-wrapper"],
)
def test_maven(root: Path, files: list[str], x: str) -> None:
    for f in files:
        write(root, f, "x\n")
    assert answers(root) == {**base(), **maven(x)}


@pytest.mark.parametrize(
    ("files", "x"),
    [
        (["build.gradle"], "gradle"),
        (["build.gradle.kts"], "gradle"),
        (["settings.gradle"], "gradle"),
        (["settings.gradle.kts"], "gradle"),
        (["gradlew"], "./gradlew"),
        (["build.gradle.kts", "settings.gradle.kts", "gradlew"], "./gradlew"),
    ],
    ids=["build", "build-kts", "settings", "settings-kts", "wrapper-only", "kts-and-wrapper"],
)
def test_gradle(root: Path, files: list[str], x: str) -> None:
    for f in files:
        write(root, f, "x\n")
    assert answers(root) == {**base(), **gradle(x)}


@pytest.mark.parametrize(
    ("files", "stack"),
    [
        (["pom.xml", "build.gradle"], "java-maven"),
        (["mvnw", "gradlew"], "java-maven"),
        (["pom.xml", "package.json"], "java-maven"),
        (["build.gradle.kts", "package.json"], "java-gradle"),
        (["pom.xml", "build.gradle", "package.json"], "java-maven"),
    ],
)
def test_precedence(root: Path, files: list[str], stack: str) -> None:
    for f in files:
        write(root, f, "{}\n" if f == "package.json" else "x\n")
    assert answers(root)["stack"] == stack


def test_maven_wrapper_decides_even_with_gradle_wrapper(root: Path) -> None:
    write(root, "pom.xml", "x\n")
    write(root, "gradlew", "x\n")
    assert answers(root) == {**base(), **maven("mvn")}


@pytest.mark.parametrize(
    ("locks", "pm"),
    [
        ([], "npm"),
        (["package-lock.json"], "npm"),
        (["pnpm-lock.yaml"], "pnpm"),
        (["yarn.lock"], "yarn"),
        (["pnpm-lock.yaml", "yarn.lock"], "pnpm"),
    ],
    ids=["none", "npm-lock", "pnpm", "yarn", "pnpm-over-yarn"],
)
def test_node_package_manager(root: Path, locks: list[str], pm: str) -> None:
    package_json(root, {"test": "jest"})
    for f in locks:
        write(root, f, "x\n")
    assert answers(root) == {
        **base(),
        "stack": "node",
        "test_cmd": f"{pm} test",
        "single_test_cmd": f"{pm} test -- {{test}}",
        "verify_cmd": f"{pm} test",
    }


def test_node_all_scripts(root: Path) -> None:
    package_json(root, {"build": "tsc", "test": "jest", "lint": "eslint .", "verify": "x"})
    write(root, "pnpm-lock.yaml", "x\n")
    assert answers(root) == {
        **base(),
        "stack": "node",
        "build_cmd": "pnpm run build",
        "test_cmd": "pnpm test",
        "verify_cmd": "pnpm run verify",
        "single_test_cmd": "pnpm test -- {test}",
        "lint_cmd": "pnpm run lint",
    }


@pytest.mark.parametrize("scripts", [None, {}], ids=["no-scripts-key", "empty-scripts"])
def test_node_no_scripts(root: Path, scripts: dict[str, str] | None) -> None:
    package_json(root, scripts)
    got = answers(root)
    assert got == {
        **base(),
        "stack": "node",
        "test_cmd": "npm test",
        "single_test_cmd": "npm test -- {test}",
        "verify_cmd": "npm test",
    }


def test_node_build_only(root: Path) -> None:
    package_json(root, {"build": "tsc"})
    write(root, "yarn.lock", "x\n")
    got = answers(root)
    assert got["build_cmd"] == "yarn run build"
    assert "lint_cmd" not in got
    assert got["verify_cmd"] == "yarn test"


def test_node_lint_only(root: Path) -> None:
    package_json(root, {"lint": "eslint ."})
    got = answers(root)
    assert got["lint_cmd"] == "npm run lint"
    assert "build_cmd" not in got
    assert got["verify_cmd"] == "npm test"


@pytest.mark.parametrize(
    "content",
    ['{"scripts": {"build": "tsc",', "\x00not json", "[1, 2]"],
    ids=["truncated", "garbage", "not-an-object"],
)
def test_node_invalid_package_json(root: Path, content: str) -> None:
    write(root, "package.json", content)
    det = detect_mod().detect(root)
    assert det.answers["stack"] == "node"
    assert "build_cmd" not in det.answers
    assert "lint_cmd" not in det.answers
    if "verify_cmd" in det.answers:
        assert det.answers["verify_cmd"] == det.answers.get("test_cmd")


@pytest.mark.parametrize(
    "content", ['{"scripts": {"build": "tsc",', "\x00not json"], ids=["truncated", "garbage"]
)
def test_node_invalid_package_json_noted(root: Path, content: str) -> None:
    write(root, "package.json", content)
    det = detect_mod().detect(root)
    assert det.notes, "an invalid package.json must leave a note"
    assert any("package.json" in n for n in det.notes), det.notes


def test_node_non_utf8_package_json(root: Path) -> None:
    (root / "package.json").write_bytes(b'{"scripts": {"build": "\xff\xfe"}}')
    det = detect_mod().detect(root)
    assert det.answers["stack"] == "node"
    assert "build_cmd" not in det.answers


# --- C38 protected_paths, use_orca, agents ----------------------------------------------------


def test_protected_paths_with_migration_dir(root: Path) -> None:
    (root / "src/main/resources/db/migration").mkdir(parents=True)
    assert answers(root)["protected_paths"] == [MIGRATION, LEGACY]


def test_protected_paths_without_migration_dir(root: Path) -> None:
    (root / "src/main/resources/db").mkdir(parents=True)
    assert answers(root)["protected_paths"] == [LEGACY]


def test_protected_paths_migration_is_a_file(root: Path) -> None:
    write(root, "src/main/resources/db/migration", "not a dir\n")
    assert answers(root)["protected_paths"] == [LEGACY]


def test_use_orca_false(root: Path) -> None:
    assert answers(root)["use_orca"] is False


def test_use_orca_from_file(root: Path) -> None:
    write(root, "orca.yaml", "worktrees: {}\n")
    assert answers(root)["use_orca"] is True


def test_use_orca_from_which(root: Path, which: Callable[..., None]) -> None:
    which("orca")
    assert answers(root)["use_orca"] is True


def test_no_agents(root: Path) -> None:
    assert detect_mod().detect(root).agents == []


@pytest.mark.parametrize(
    ("dir_", "agent"),
    [(".claude", "claude"), (".codex", "codex"), (".opencode", "opencode"), (".kiro", "kiro")],
)
def test_agent_from_dir(root: Path, dir_: str, agent: str) -> None:
    (root / dir_).mkdir()
    assert detect_mod().detect(root).agents == [agent]


@pytest.mark.parametrize(
    ("tool", "agent"),
    [("claude", "claude"), ("codex", "codex"), ("opencode", "opencode"), ("kiro-cli", "kiro")],
)
def test_agent_from_which(root: Path, which: Callable[..., None], tool: str, agent: str) -> None:
    which(tool)
    assert detect_mod().detect(root).agents == [agent]


def test_kiro_needs_kiro_cli(root: Path, which: Callable[..., None]) -> None:
    which("kiro")
    assert detect_mod().detect(root).agents == []


def test_agent_dir_must_be_a_directory(root: Path) -> None:
    write(root, ".claude", "not a dir\n")
    assert detect_mod().detect(root).agents == []


def test_agents_sorted_unique(root: Path, which: Callable[..., None]) -> None:
    for d in [".opencode", ".claude", ".kiro"]:
        (root / d).mkdir()
    which("claude", "codex", "kiro-cli")
    assert detect_mod().detect(root).agents == ["claude", "codex", "kiro", "opencode"]


# --- C39 collect_answers -----------------------------------------------------------------------


def collect(root: Path, **kwargs: Any) -> dict[str, Any]:
    return detect_mod().collect_answers(root, **kwargs)


def write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_collect_detection_only(root: Path) -> None:
    write(root, "pom.xml", "x\n")
    assert collect(root) == {**base(), **maven("mvn")}


def test_collect_layers(root: Path, tmp_path: Path) -> None:
    write(root, "pom.xml", "x\n")
    write_yaml(
        root / ".copier-answers.yml",
        {
            "_commit": "v0.3.0",
            "_src_path": ".kuanflow/cache/template-repo",
            "kuanflow_version": "0.3.0",
            "project_name": "from-answers",
            "stack": "java-gradle",
            "test_cmd": "answers test",
            "jira_project_key": "ORD",
        },
    )
    data = write_yaml(tmp_path / "data.yml", {"stack": "node", "jira_project_key": "PAY"})
    got = collect(root, data_file=data)
    assert got["project_name"] == "from-answers"  # answers file beats detection
    assert got["test_cmd"] == "answers test"
    assert got["stack"] == "node"  # data file beats answers file
    assert got["jira_project_key"] == "PAY"
    assert got["build_cmd"] == "mvn -q -DskipTests package"  # detection kept where not overridden
    assert "kuanflow_version" not in got
    assert not any(k.startswith("_") for k in got), got


def test_collect_answers_file_underscore_and_version_ignored(root: Path) -> None:
    write_yaml(
        root / ".copier-answers.yml",
        {"_commit": "v0.3.0", "_src_path": "x", "kuanflow_version": "0.3.0", "fintech": False},
    )
    assert collect(root) == {**base(), "stack": "other", "fintech": False}


def test_collect_data_file_only_keys(root: Path, tmp_path: Path) -> None:
    data = write_yaml(
        tmp_path / "d.yml", {"services": ["svc-a"], "protected_paths": ["x/**"], "fintech": True}
    )
    got = collect(root, data_file=data)
    assert got["services"] == ["svc-a"]
    assert got["protected_paths"] == ["x/**"]
    assert got["fintech"] is True


@pytest.mark.parametrize("source", ["none", "answers", "data"])
def test_collect_personal_forces_none(root: Path, tmp_path: Path, source: str) -> None:
    kwargs: dict[str, Any] = {"personal": True}
    if source == "answers":
        write_yaml(root / ".copier-answers.yml", {"artifacts_commit": "full"})
    if source == "data":
        kwargs["data_file"] = write_yaml(tmp_path / "d.yml", {"artifacts_commit": "minimal"})
    assert collect(root, **kwargs)["artifacts_commit"] == "none"


def test_collect_not_personal_keeps_artifacts_commit(root: Path, tmp_path: Path) -> None:
    data = write_yaml(tmp_path / "d.yml", {"artifacts_commit": "full"})
    assert collect(root, data_file=data)["artifacts_commit"] == "full"


def test_collect_data_file_missing(root: Path, tmp_path: Path) -> None:
    missing = tmp_path / "missing.yml"
    with pytest.raises(answers_error(), match="missing.yml"):
        collect(root, data_file=missing)


@pytest.mark.parametrize(
    "content", ["- a\n- b\n", "just a string\n", "42\n"], ids=["list", "str", "int"]
)
def test_collect_data_file_not_mapping(root: Path, tmp_path: Path, content: str) -> None:
    f = write(tmp_path, "bad.yml", content)
    with pytest.raises(answers_error(), match="bad.yml"):
        collect(root, data_file=f)


def test_collect_data_file_yaml_error(root: Path, tmp_path: Path) -> None:
    f = write(tmp_path, "broken.yml", "project_name: [unclosed\n  stack: : :\n")
    with pytest.raises(answers_error(), match="broken.yml"):
        collect(root, data_file=f)


@pytest.mark.parametrize("key", ["no_such_question", "kuanflow_version", "_commit", "org_name"])
def test_collect_data_file_bad_key(root: Path, tmp_path: Path, key: str) -> None:
    f = write_yaml(tmp_path / "keys.yml", {"project_name": "x", key: "v"})
    with pytest.raises(answers_error()) as exc:
        collect(root, data_file=f)
    assert "keys.yml" in str(exc.value)
    assert key in str(exc.value)


# --- C39 knowledge-repo template ---------------------------------------------------------------


def test_knowledge_repo_no_detection(root: Path) -> None:
    write(root, "pom.xml", "x\n")
    (root / ".claude").mkdir()
    write(root, "orca.yaml", "x: 1\n")
    assert collect(root, template="knowledge-repo") == {}


def test_knowledge_repo_layers(root: Path, tmp_path: Path) -> None:
    write_yaml(
        root / ".copier-answers.yml",
        {"_commit": "v0.3.0", "kuanflow_version": "0.3.0", "org_name": "old-org"},
    )
    assert collect(root, template="knowledge-repo") == {"org_name": "old-org"}
    data = write_yaml(tmp_path / "k.yml", {"org_name": "Tổ chức A"})
    assert collect(root, template="knowledge-repo", data_file=data) == {"org_name": "Tổ chức A"}


@pytest.mark.parametrize("key", ["stack", "project_name", "kuanflow_version"])
def test_knowledge_repo_rejects_project_questions(root: Path, tmp_path: Path, key: str) -> None:
    f = write_yaml(tmp_path / "k.yml", {"org_name": "o", key: "x"})
    with pytest.raises(answers_error()) as exc:
        collect(root, template="knowledge-repo", data_file=f)
    assert key in str(exc.value)
