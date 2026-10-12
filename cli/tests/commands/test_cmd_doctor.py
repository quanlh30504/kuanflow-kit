"""Contract tests C49: `kuanflow doctor` and `kuanflow_cli.doctor.run`."""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    assert_error,
    assert_ok,
    build,
    commit_all,
    describe,
    doctor_checks,
    doctor_summary,
    edit_block_body,
    invoke,
    read_manifest,
    set_which,
    write,
    write_manifest,
)

PROJECT_CHECKS = [
    "manifest",
    "config",
    "commands",
    "scripts",
    "python",
    "blocks",
    "version",
    "answers",
]
KNOWLEDGE_CHECKS = ["manifest", "version", "answers"]
LINE = re.compile(r"^(OK|WARN|FAIL) {1,3}[a-z]+: ")


def fake_python(tmp_path: Path, env: pytest.MonkeyPatch, *, ok: bool) -> None:
    """Put a `python3` first on PATH that succeeds (`import yaml` works) or fails."""
    bindir = tmp_path / ("bin-ok" if ok else "bin-fail")
    bindir.mkdir(exist_ok=True)
    py = bindir / "python3"
    py.write_text(f"#!/bin/sh\nexit {0 if ok else 1}\n", encoding="utf-8")
    py.chmod(0o755)
    env.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")


def installed(tmp_path: Path, name: str = "maven", *extra: str) -> Path:
    root = build(name, tmp_path / name)
    assert_ok(invoke(["init", "--yes", *extra], cwd=root))
    commit_all(root, "kuanflow init")
    return root


def doctor(root: Path, *args: str, cwd: Path | None = None) -> Any:
    return invoke(["doctor", *args], cwd=cwd or root)


def levels(result: Any) -> dict[str, str]:
    return {name: level for level, name, _ in doctor_checks(result.stdout)}


def test_doctor_all_ok_format(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    result = doctor(root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    checks = doctor_checks(result.stdout)
    assert [name for _, name, _ in checks] == PROJECT_CHECKS
    assert all(level == "OK" for level, _, _ in checks), describe(result)
    check_lines = [ln for ln in lines if LINE.match(ln)]
    assert len(check_lines) == len(PROJECT_CHECKS)
    for ln in check_lines:
        assert ln.startswith("OK   "), ln  # "{level:<4} {name}: {message}"
    assert lines[-1] == f"doctor: {len(PROJECT_CHECKS)} ok, 0 warn, 0 fail"


def test_doctor_unresolvable_commands_warn(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path, "empty")  # make build / make test / make verify
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["commands"] == "WARN"
    assert doctor_summary(result.stdout) == (len(PROJECT_CHECKS) - 1, 1, 0)
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("WARN commands: "))
    assert "make" in line
    set_which(env, {"make"})
    resolved = doctor(root)
    assert_ok(resolved)
    assert levels(resolved)["commands"] == "OK"


def test_doctor_non_executable_command_warns(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    (root / "mvnw").chmod(0o644)
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["commands"] == "WARN"
    (root / "mvnw").unlink()
    missing = doctor(root)
    assert_ok(missing)
    assert levels(missing)["commands"] == "WARN"


def test_doctor_commands_never_executed(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    marker = tmp_path / "ran"
    write(root, "mvnw", f"#!/bin/sh\ntouch {marker}\n", mode=0o755)
    assert_ok(doctor(root))
    assert not marker.exists()


@pytest.mark.parametrize("damage", ["chmod", "content", "delete"])
def test_doctor_script_fail(tmp_path: Path, env: pytest.MonkeyPatch, damage: str) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    script = root / ".kuanflow/scripts/guard-bash.sh"
    if damage == "chmod":
        script.chmod(0o644)
    elif damage == "content":
        script.write_text(script.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    else:
        script.unlink()
    result = doctor(root)
    assert result.exit_code == 1, describe(result)
    assert levels(result)["scripts"] == "FAIL"
    assert doctor_summary(result.stdout)[2] == 1
    assert "guard-bash.sh" in next(
        ln for ln in result.stdout.splitlines() if ln.startswith("FAIL scripts: ")
    )


def test_doctor_python_warn(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=False)
    root = installed(tmp_path)
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["python"] == "WARN"


def test_doctor_block_edited_warn(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    edit_block_body(root / "AGENTS.md", "html", "- my own rule\n")
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["blocks"] == "WARN"


@pytest.mark.parametrize("damage", ["file-deleted", "block-removed", "markers-broken"])
def test_doctor_block_missing_fail(tmp_path: Path, env: pytest.MonkeyPatch, damage: str) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    path = root / "CLAUDE.md"
    text = path.read_text(encoding="utf-8")
    if damage == "file-deleted":
        path.unlink()
    elif damage == "block-removed":
        path.write_text(text[text.index("<!-- kuanflow:end -->\n") + 22 :], encoding="utf-8")
    else:
        path.write_text(text.replace("<!-- kuanflow:end -->\n", ""), encoding="utf-8")
    result = doctor(root)
    assert result.exit_code == 1, describe(result)
    assert levels(result)["blocks"] == "FAIL"


def test_doctor_min_version_above_cli_fails(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    cfg = root / ".kuanflow/config.yaml"
    text = cfg.read_text(encoding="utf-8")
    new = re.sub(r'min_version: "[^"]*"', 'min_version: "99.0.0"', text)
    assert new != text
    cfg.write_text(new, encoding="utf-8")
    result = doctor(root)
    assert result.exit_code == 1, describe(result)
    assert levels(result)["version"] == "FAIL"
    assert levels(result)["config"] == "OK"


def test_doctor_manifest_version_differs_warns(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    data = read_manifest(root)
    data["kuanflow_version"] = "0.0.1"
    write_manifest(root, data)
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["version"] == "WARN"
    assert levels(result)["answers"] == "WARN"  # _commit is v<CLI version>, not v0.0.1


def test_doctor_answers_commit_mismatch_warns(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    answers = root / ".copier-answers.yml"
    text = answers.read_text(encoding="utf-8")
    new = re.sub(r"(?m)^_commit: .*$", "_commit: v0.0.0", text)
    assert new != text
    answers.write_text(new, encoding="utf-8")
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["answers"] == "WARN"


@pytest.mark.parametrize("damage", ["invalid-yaml", "schema", "missing"])
def test_doctor_config_fail(tmp_path: Path, env: pytest.MonkeyPatch, damage: str) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    cfg = root / ".kuanflow/config.yaml"
    if damage == "invalid-yaml":
        cfg.write_text("commands: [unclosed\n", encoding="utf-8")
    elif damage == "schema":
        cfg.write_text("schema_version: 1\nproject: 42\n", encoding="utf-8")
    else:
        cfg.unlink()
    result = doctor(root)
    assert result.exit_code == 1, describe(result)
    assert levels(result)["config"] == "FAIL"


@pytest.mark.parametrize("damage", ["absent", "invalid"])
def test_doctor_manifest_fail_skips_rest(
    tmp_path: Path, env: pytest.MonkeyPatch, damage: str
) -> None:
    if damage == "absent":
        root = build("maven", tmp_path / "maven")
    else:
        root = installed(tmp_path)
        (root / ".kuanflow/manifest.json").write_text("[]\n", encoding="utf-8")
    result = doctor(root)
    assert result.exit_code == 1, describe(result)
    checks = doctor_checks(result.stdout)
    assert [(level, name) for level, name, _ in checks] == [("FAIL", "manifest")]
    assert result.stdout.splitlines()[-1] == "doctor: 0 ok, 0 warn, 1 fail"


def test_doctor_knowledge_repo_three_checks(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path, "empty", "--template", "knowledge-repo")
    result = doctor(root)
    assert_ok(result)
    assert [name for _, name, _ in doctor_checks(result.stdout)] == KNOWLEDGE_CHECKS
    assert result.stdout.splitlines()[-1] == "doctor: 3 ok, 0 warn, 0 fail"


def test_doctor_personal_mode(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = build("maven", tmp_path / "maven")
    assert_ok(invoke(["init", "--personal", "--yes"], cwd=root))
    result = doctor(root)
    assert_ok(result)
    assert levels(result)["blocks"] == "OK"
    exclude = root / ".git/info/exclude"
    text = exclude.read_text(encoding="utf-8")
    exclude.write_text(text.replace("# kuanflow:end\n", ""), encoding="utf-8")
    broken = doctor(root)
    assert broken.exit_code == 1, describe(broken)
    assert levels(broken)["blocks"] == "FAIL"


def test_doctor_agent_option_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    assert_error(doctor(root, "--agent", "x"))


def test_doctor_root_option(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = doctor(root, "--root", str(root), cwd=elsewhere)
    assert doctor_summary(result.stdout)[2] == 0, describe(result)


def test_doctor_run_api(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    fake_python(tmp_path, env, ok=True)
    root = installed(tmp_path)
    mod = importlib.import_module("kuanflow_cli.doctor")
    checks = mod.run(root)
    assert [c.name for c in checks] == PROJECT_CHECKS
    assert {c.level for c in checks} == {"OK"}
    assert all(isinstance(c.message, str) for c in checks)
    (root / ".kuanflow/scripts/load-config.sh").chmod(0o644)
    by_name = {c.name: c.level for c in mod.run(root)}
    assert by_name["scripts"] == "FAIL"
