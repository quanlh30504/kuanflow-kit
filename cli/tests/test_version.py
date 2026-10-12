"""Contract tests C1/C2: VERSION file, CLI package metadata and `kuanflow --version`."""

import importlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "VERSION"
PYPROJECT = REPO_ROOT / "cli" / "pyproject.toml"

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def semver_to_pep440(version: str) -> str:
    """Convert the in-scope SemVer forms to PEP 440."""
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(dev|beta\.(\d+)|rc\.(\d+)))?", version)
    if m is None:
        raise ValueError(f"unsupported version form: {version!r}")
    base, pre, beta, rc = m.groups()
    if pre is None:
        return base
    if pre == "dev":
        return f"{base}.dev0"
    if beta is not None:
        return f"{base}b{beta}"
    return f"{base}rc{rc}"


@pytest.mark.parametrize(
    ("semver", "pep440"),
    [
        ("0.1.0-dev", "0.1.0.dev0"),
        ("1.2.3-beta.4", "1.2.3b4"),
        ("1.2.3-rc.1", "1.2.3rc1"),
        ("1.2.3", "1.2.3"),
    ],
)
def test_semver_to_pep440_helper(semver: str, pep440: str) -> None:
    assert semver_to_pep440(semver) == pep440


def _version_text() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def _expected_pep440() -> str:
    return semver_to_pep440(_version_text())


def test_version_file_is_single_semver_line() -> None:
    raw = VERSION_FILE.read_text(encoding="utf-8")
    assert raw.endswith("\n"), "VERSION must end with a newline"
    lines = raw.splitlines()
    assert len(lines) == 1, "VERSION must contain exactly one line"
    assert SEMVER_RE.match(lines[0]), f"VERSION is not SemVer 2.0: {lines[0]!r}"


def test_pyproject_metadata() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "kuanflow-cli"
    assert project["requires-python"] == ">=3.11"
    assert "version" in project.get("dynamic", []), "version must be dynamic"
    assert project["scripts"]["kuanflow"] == "kuanflow_cli.main:app"
    assert data["build-system"]["build-backend"].startswith("hatchling")


def test_package_dunder_version() -> None:
    pkg = importlib.import_module("kuanflow_cli")
    assert pkg.__version__ == _expected_pep440()


def test_cli_version_in_process() -> None:
    from typer.testing import CliRunner

    app = importlib.import_module("kuanflow_cli.main").app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"kuanflow {_expected_pep440()}"


def test_cli_version_console_script() -> None:
    script = Path(sys.executable).parent / "kuanflow"
    if not script.exists():
        pytest.skip(f"console script not installed next to interpreter: {script}")
    proc = subprocess.run(
        [str(script), "--version"], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == f"kuanflow {_expected_pep440()}"
