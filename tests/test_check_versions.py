"""Contract tests C4: tests/check_versions.py."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tests" / "check_versions.py"

PYPROJECT_DYNAMIC = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kuanflow-cli"
dynamic = ["version"]
requires-python = ">=3.11"
"""


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def make_tree(
    root: Path,
    version: str | None = "0.1.0-dev",
    plugin: str | None = None,
    market_meta: str | None = None,
    market_entry: str | None = None,
) -> Path:
    if version is not None:
        (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT_DYNAMIC, encoding="utf-8")
    if plugin is not None:
        d = root / "plugins" / "kuanflow" / ".claude-plugin"
        d.mkdir(parents=True)
        (d / "plugin.json").write_text(
            json.dumps({"name": "kuanflow", "version": plugin}), encoding="utf-8"
        )
    if market_meta is not None or market_entry is not None:
        d = root / ".claude-plugin"
        d.mkdir()
        data = {
            "name": "kuanflow-marketplace",
            "metadata": {"version": market_meta},
            "plugins": [
                {"name": "other", "source": "./plugins/other", "version": "9.9.9"},
                {"name": "kuanflow", "source": "./plugins/kuanflow", "version": market_entry},
            ],
        }
        (d / "marketplace.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_only_version_and_cli_agree(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path))
    assert proc.returncode == 0, proc.stderr


def test_all_sources_agree(tmp_path: Path) -> None:
    v = "0.1.0-dev"
    proc = run(make_tree(tmp_path, v, plugin=v, market_meta=v, market_entry=v))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("bad", ["0.1", "v0.1.0", "0.1.0-", "01.0.0", "not-a-version"])
def test_invalid_semver_version(tmp_path: Path, bad: str) -> None:
    proc = run(make_tree(tmp_path, bad))
    assert proc.returncode == 1


def test_missing_version_file(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path, version=None))
    assert proc.returncode == 1


def test_plugin_json_mismatch(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path, "0.1.0-dev", plugin="0.2.0"))
    assert proc.returncode == 1
    assert "plugin.json" in proc.stderr


def test_marketplace_metadata_mismatch(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path, "0.1.0-dev", market_meta="0.0.9", market_entry="0.1.0-dev"))
    assert proc.returncode == 1
    assert "marketplace.json" in proc.stderr


def test_marketplace_plugin_entry_mismatch(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path, "0.1.0-dev", market_meta="0.1.0-dev", market_entry="0.0.9"))
    assert proc.returncode == 1
    assert "marketplace.json" in proc.stderr


def test_multiple_mismatches_one_line_each(tmp_path: Path) -> None:
    tree = make_tree(
        tmp_path, "0.1.0-dev", plugin="0.2.0", market_meta="0.3.0", market_entry="0.1.0-dev"
    )
    proc = run(tree)
    assert proc.returncode == 1
    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    assert len(lines) >= 2


def test_matching_tag(tmp_path: Path) -> None:
    proc = run(make_tree(tmp_path, "0.1.0-dev"), "--tag", "v0.1.0-dev")
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("tag", ["v0.1.0", "0.1.0-dev", "v0.2.0-dev"])
def test_wrong_tag(tmp_path: Path, tag: str) -> None:
    proc = run(make_tree(tmp_path, "0.1.0-dev"), "--tag", tag)
    assert proc.returncode == 1


def test_real_repo_root() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr


# --- Fix round 1: C4a and agreement with the C9 converter ---------------------------------------


def _load_tables() -> ModuleType:
    path = REPO_ROOT / "cli" / "tests" / "test_semver.py"
    spec = importlib.util.spec_from_file_location("kf_test_semver_tables_cv", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_TABLES = _load_tables()

PYPROJECT_STATIC = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kuanflow-cli"
version = "{version}"
requires-python = ">=3.11"
"""


def make_static_tree(root: Path, version_text: str, static_version: str) -> Path:
    (root / "VERSION").write_text(version_text, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        PYPROJECT_STATIC.format(version=static_version), encoding="utf-8"
    )
    return root


def make_dynamic_tree(root: Path, version_text: str) -> Path:
    (root / "VERSION").write_text(version_text, encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT_DYNAMIC, encoding="utf-8")
    return root


@pytest.mark.parametrize("text", ["0.1.0-dev\n0.2.0\n", "0.1.0-dev\n\n", "\n0.1.0-dev\n"])
def test_multiline_version_rejected(tmp_path: Path, text: str) -> None:
    proc = run(make_dynamic_tree(tmp_path, text))
    assert proc.returncode == 1


def test_version_without_trailing_newline_accepted(tmp_path: Path) -> None:
    proc = run(make_dynamic_tree(tmp_path, "0.1.0-dev"))
    assert proc.returncode == 0, proc.stderr


def _assert_one_line_error(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    assert len(lines) == 1, proc.stderr


@pytest.mark.parametrize("content", ["[]", '["kuanflow", "0.1.0-dev"]', '"0.1.0-dev"', "42"])
def test_plugin_json_not_object(tmp_path: Path, content: str) -> None:
    make_tree(tmp_path)
    d = tmp_path / "plugins" / "kuanflow" / ".claude-plugin"
    d.mkdir(parents=True)
    (d / "plugin.json").write_text(content, encoding="utf-8")
    _assert_one_line_error(run(tmp_path))


@pytest.mark.parametrize("content", ["[]", "[{}]", "null"])
def test_marketplace_json_not_object(tmp_path: Path, content: str) -> None:
    make_tree(tmp_path)
    d = tmp_path / ".claude-plugin"
    d.mkdir()
    (d / "marketplace.json").write_text(content, encoding="utf-8")
    _assert_one_line_error(run(tmp_path))


@pytest.mark.parametrize("where", ["plugin", "marketplace"])
def test_invalid_json(tmp_path: Path, where: str) -> None:
    make_tree(tmp_path)
    if where == "plugin":
        d = tmp_path / "plugins" / "kuanflow" / ".claude-plugin"
        name = "plugin.json"
    else:
        d = tmp_path / ".claude-plugin"
        name = "marketplace.json"
    d.mkdir(parents=True)
    (d / name).write_text('{"version": "0.1.0-dev",', encoding="utf-8")
    _assert_one_line_error(run(tmp_path))


@pytest.mark.parametrize(("semver", "pep440"), _TABLES.VALID)
def test_static_version_agrees_with_c9_valid(tmp_path: Path, semver: str, pep440: str) -> None:
    proc = run(make_static_tree(tmp_path, semver + "\n", pep440))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(("semver", "pep440"), _TABLES.VALID)
def test_static_version_mismatch_detected(tmp_path: Path, semver: str, pep440: str) -> None:
    proc = run(make_static_tree(tmp_path, semver + "\n", pep440 + ".post1"))
    assert proc.returncode == 1
    assert proc.stderr.strip()


@pytest.mark.parametrize("bad", _TABLES.INVALID)
def test_static_version_c9_invalid_rejected(tmp_path: Path, bad: str) -> None:
    proc = run(make_static_tree(tmp_path, bad + "\n", "0.0.0"))
    assert proc.returncode == 1


@pytest.mark.parametrize("bad", _TABLES.INVALID)
def test_dynamic_version_c9_invalid_rejected(tmp_path: Path, bad: str) -> None:
    proc = run(make_dynamic_tree(tmp_path, bad + "\n"))
    assert proc.returncode == 1


@pytest.mark.parametrize(("semver", "_pep440"), _TABLES.VALID)
def test_dynamic_version_c9_valid_accepted(tmp_path: Path, semver: str, _pep440: str) -> None:
    proc = run(make_dynamic_tree(tmp_path, semver + "\n"), "--tag", "v" + semver)
    assert proc.returncode == 0, proc.stderr


def test_checker_uses_shared_converter() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "kuanflow_cli" in source and "semver.py" in source
