"""Contract tests C36a, C36b, C53: error output, exit codes and command wiring."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest
from conftest import assert_error, assert_ok, build, describe, invoke

COMMANDS = ["init", "status", "doctor", "promote", "uninstall"]
RUN_KWARGS = {
    "init": {
        "here",
        "agent",
        "personal",
        "template",
        "yes",
        "dry_run",
        "root",
        "data_file",
        "force",
    },
    "status": {"root"},
    "doctor": {"agent", "root"},
    "promote": {"draft", "dry_run", "root"},
    "uninstall": {"dry_run", "force", "root"},
}


def registered() -> set[str]:
    from typer.main import get_command

    group = get_command(importlib.import_module("kuanflow_cli.main").app)
    return set(getattr(group, "commands", {}))


def usage_error(result: Any) -> None:
    assert result.exit_code == 1, describe(result)  # never Click's 2
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


@pytest.mark.parametrize(
    "args",
    [
        ["nosuch"],
        ["init", "--nosuch"],
        ["status", "--nosuch"],
        ["doctor", "--nosuch"],
        ["uninstall", "--nosuch"],
        ["promote"],
        ["promote", "a.md", "b.md"],
        ["init", "--template"],
        ["init", "--root"],
    ],
    ids=lambda a: " ".join(a) or "none",
)
def test_usage_errors_exit_1(tmp_path: Path, env: pytest.MonkeyPatch, args: list[str]) -> None:
    root = build("empty", tmp_path / "empty")
    result = invoke(args, cwd=root)
    usage_error(result)
    assert result.stderr.strip(), describe(result)
    assert not (root / ".kuanflow").exists()


@pytest.mark.parametrize("name", ["upgrade", "agent", "self"])
def test_later_commands_not_registered(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    result = invoke([name], cwd=tmp_path)
    usage_error(result)
    assert name not in registered()


@pytest.mark.parametrize("name", COMMANDS)
def test_commands_registered(tmp_path: Path, env: pytest.MonkeyPatch, name: str) -> None:
    result = invoke([name, "--help"], cwd=tmp_path)
    assert_ok(result)
    assert name in registered()


@pytest.mark.parametrize("name", COMMANDS)
def test_command_modules_have_run(name: str) -> None:
    mod = importlib.import_module(f"kuanflow_cli.commands.{name}")
    run = mod.run
    assert callable(run)
    params = inspect.signature(run).parameters
    assert RUN_KWARGS[name] <= set(params), sorted(params)
    for pname in RUN_KWARGS[name] - {"draft"}:
        assert params[pname].kind in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )


def test_version_unchanged(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    from kuanflow_cli import __version__

    result = invoke(["--version"], cwd=tmp_path)
    assert_ok(result)
    assert result.stdout == f"kuanflow {__version__}\n"


@pytest.mark.parametrize(
    "args",
    [["status"], ["doctor"], ["uninstall"], ["init", "--yes"], ["promote", "adr-x.md"]],
    ids=lambda a: a[0],
)
def test_kuanflow_error_outside_git(
    tmp_path: Path, env: pytest.MonkeyPatch, args: list[str]
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "adr-x.md").write_text("# X\n", encoding="utf-8")
    result = invoke(args, cwd=plain)
    if args == ["doctor"]:
        # Doctor reports the problem as a FAIL check or as an error; both exit 1 cleanly.
        assert result.exit_code == 1, describe(result)
        assert "Traceback" not in result.output
        return
    assert_error(result)
    assert result.stderr.lstrip().startswith("error: "), describe(result)
    assert "error: " not in result.stdout


def test_errors_never_exit_2_or_3(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write_dirty = root / "dirty.txt"
    write_dirty.write_text("x\n", encoding="utf-8")
    for args in (["init", "--yes"], ["status"], ["uninstall"], ["init", "--agent", "codex"]):
        result = invoke(args, cwd=root)
        assert result.exit_code == 1, describe(result)


def test_dirty_tree_error_lists_paths(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    (root / "dirty.txt").write_text("x\n", encoding="utf-8")
    assert_error(invoke(["init", "--yes"], cwd=root), "dirty.txt")
