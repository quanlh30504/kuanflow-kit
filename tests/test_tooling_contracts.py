"""Contract tests C2a, C3a, C7a, C8a: deps, ruff config, make verify / CI, CHANGELOG, CODEOWNERS."""

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- C2a ---------------------------------------------------------------------------------------


def _requirement_name(spec: str) -> str:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    assert m, f"unparseable requirement: {spec!r}"
    return re.sub(r"[-_.]+", "-", m.group(1)).lower()


def _runtime_deps() -> dict[str, str]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {_requirement_name(s): s for s in data["project"]["dependencies"]}


@pytest.mark.parametrize("name", ["copier", "typer", "pyyaml", "tomlkit", "rich", "jsonschema"])
def test_runtime_dependency_present(name: str) -> None:
    assert name in _runtime_deps()


def test_copier_pin() -> None:
    spec = _runtime_deps()["copier"].replace(" ", "")
    assert ">=9.18.2" in spec
    assert "<10" in spec


# --- C3a ---------------------------------------------------------------------------------------


def test_ruff_config() -> None:
    data = tomllib.loads((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"))
    assert data.get("target-version") == "py311"
    assert data.get("line-length") == 100


# --- C7a ---------------------------------------------------------------------------------------

# Each C7 command, identified by its tail; all but bats go through `uv run` (C7r: no --project).
C7_COMMANDS: list[tuple[str, bool]] = [
    ("ruff check .", True),
    ("ruff format --check .", True),
    ("pytest -q", True),
    ("bats tests/bats", False),
    ("python tests/check_skills.py plugins/kuanflow", True),
    ("python tests/check_versions.py", True),
]


@pytest.fixture(scope="module")
def make_verify_lines() -> list[str]:
    make = shutil.which("make")
    assert make, "make not found"
    proc = subprocess.run(
        [make, "-n", "verify"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def _matches(line: str, tail: str, via_uv: bool) -> bool:
    if not re.search(r"(^|\s)" + re.escape(tail) + r"$", line):
        return False
    if via_uv:
        return "uv run" in line and "--project" not in line
    return True


def test_make_verify_runs_six_commands_in_order(make_verify_lines: list[str]) -> None:
    positions = []
    for tail, via_uv in C7_COMMANDS:
        idx = [i for i, ln in enumerate(make_verify_lines) if _matches(ln, tail, via_uv)]
        assert idx, f"`make verify` does not run {tail!r}: {make_verify_lines}"
        positions.append(idx[0])
    assert positions == sorted(positions), f"C7 order broken: {make_verify_lines}"
    assert len(set(positions)) == len(positions)


def test_make_verify_uv_run_is_locked(make_verify_lines: list[str]) -> None:
    uv_lines = [ln for ln in make_verify_lines if "uv run" in ln]
    assert uv_lines
    for ln in uv_lines:
        assert "--locked" in ln.split(), f"`uv run` without --locked: {ln!r}"


@pytest.fixture(scope="module")
def ci() -> dict:
    data = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    assert isinstance(data, dict)
    return data


def _python_matrix_jobs(ci: dict) -> list[tuple[dict, str]]:
    found = []
    for job in (ci.get("jobs") or {}).values():
        matrix = ((job or {}).get("strategy") or {}).get("matrix") or {}
        for key, values in matrix.items():
            if isinstance(values, list) and {"3.11", "3.13"} <= {str(v) for v in values}:
                found.append((job, key))
    return found


def test_ci_python_matrix(ci: dict) -> None:
    assert _python_matrix_jobs(ci), "no CI job with a matrix containing 3.11 and 3.13"


def test_ci_uv_python_from_matrix(ci: dict) -> None:
    ok = False
    for job, key in _python_matrix_jobs(ci):
        envs = [job.get("env") or {}] + [s.get("env") or {} for s in job.get("steps") or []]
        for env in envs:
            value = str(env.get("UV_PYTHON", ""))
            if re.search(r"\$\{\{\s*matrix\." + re.escape(key) + r"\s*\}\}", value):
                ok = True
    assert ok, "UV_PYTHON is not set from the Python matrix"


def test_ci_runs_make_verify(ci: dict) -> None:
    for job, _key in _python_matrix_jobs(ci):
        runs = [str(s.get("run", "")) for s in job.get("steps") or []]
        if any(re.search(r"(^|\s)make verify(\s|$)", r) for r in runs):
            return
    pytest.fail("matrix job does not run `make verify`")


# --- C8a ---------------------------------------------------------------------------------------


def test_changelog_format() -> None:
    lines = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "# Changelog"
    assert "## [Unreleased]" in lines
    start = lines.index("## [Unreleased]") + 1
    section = []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        section.append(ln)
    assert any(ln.startswith("### ") for ln in section), "no ### subsection under [Unreleased]"


# PKG §14 CODEOWNERS rules.
PKG14_RULES: dict[str, set[str]] = {
    "*": {"@<org>/kuanflow-maintainers"},
    "plugins/kuanflow/skills/fintech-review/": {"@<org>/payment-leads"},
    "plugins/kuanflow/skills/debug-incident/": {"@<org>/sre-leads"},
    "plugins/kuanflow/hooks/": {"@<org>/kuanflow-maintainers", "@<org>/security"},
    "templates/": {"@<org>/kuanflow-maintainers"},
}


def _codeowners() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}
    for raw in (REPO_ROOT / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        path, *owners = line.split()
        rules[path] = owners
    return rules


@pytest.mark.parametrize("path", sorted(PKG14_RULES))
def test_codeowners_pkg14_rule(path: str) -> None:
    rules = _codeowners()
    assert path in rules, f"CODEOWNERS lacks the PKG §14 rule for {path!r}"
    assert set(rules[path]) == PKG14_RULES[path]


def test_codeowners_only_placeholder_orgs() -> None:
    rules = _codeowners()
    assert rules
    for path, owners in rules.items():
        assert owners, f"rule without owners: {path}"
        for owner in owners:
            assert re.fullmatch(r"@<org>/[a-z0-9-]+", owner), f"non-placeholder owner {owner!r}"
