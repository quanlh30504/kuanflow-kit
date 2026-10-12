"""Contract tests C9: cli/semver_pep440.py, the single SemVer -> PEP 440 converter.

VALID and INVALID are also loaded by tests/test_check_versions.py and cli/tests/test_hatch_build.py
so that every real implementation is checked against the same table.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "semver_pep440.py"

# SemVer (as written in VERSION) -> expected PEP 440 string.
VALID: list[tuple[str, str]] = [
    ("0.0.0", "0.0.0"),
    ("0.1.0", "0.1.0"),
    ("1.2.3", "1.2.3"),
    ("10.20.30", "10.20.30"),
    ("0.1.0-dev", "0.1.0.dev0"),
    ("0.1.0-dev.0", "0.1.0.dev0"),
    ("0.1.0-dev.2", "0.1.0.dev2"),
    ("1.2.3-dev.15", "1.2.3.dev15"),
    ("1.2.3-alpha.0", "1.2.3a0"),
    ("1.2.3-alpha.1", "1.2.3a1"),
    ("1.2.3-a.1", "1.2.3a1"),
    ("1.2.3-a.12", "1.2.3a12"),
    ("1.2.3-beta.2", "1.2.3b2"),
    ("1.2.3-b.2", "1.2.3b2"),
    ("1.2.3-rc.0", "1.2.3rc0"),
    ("1.2.3-rc.1", "1.2.3rc1"),
    ("1.2.3-rc.10", "1.2.3rc10"),
]

# Inputs that must raise ValueError. Entries with whitespace or that are empty are listed separately
# because they cannot be round-tripped through a VERSION file unambiguously.
INVALID: list[str] = [
    # leading zeros in the core
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "00.0.0",
    # leading zeros in N
    "1.2.3-rc.01",
    "1.2.3-dev.01",
    "1.2.3-alpha.01",
    "1.2.3-a.01",
    "1.2.3-beta.01",
    "1.2.3-b.00",
    # build metadata
    "1.2.3+build",
    "1.2.3+build.1",
    "1.2.3-rc.1+build",
    "0.1.0-dev+abc",
    # bare pre-release labels that need a number
    "1.2.3-rc",
    "1.2.3-alpha",
    "1.2.3-beta",
    "1.2.3-a",
    "1.2.3-b",
    # other pre-release forms
    "1.2.3-foo",
    "1.2.3-foo.1",
    "1.2.3-RC.1",
    "1.2.3-rc.1.2",
    "1.2.3-rc.x",
    "1.2.3-dev.",
    "1.2.3-",
    "1.2.3-post.1",
    # malformed core
    "1.2",
    "1",
    "1.2.3.4",
    "v1.2.3",
    "1.2.x",
    "a.b.c",
    "-1.2.3",
]

INVALID_WHITESPACE: list[str] = [
    "",
    " ",
    " 1.2.3",
    "1.2.3 ",
    "1.2 .3",
    "1. 2.3",
    "1.2.3- rc.1",
    "1.2.3-rc. 1",
    "1.2.3\n",
    "1.2.3\t",
]


def load_module() -> ModuleType:
    assert MODULE_PATH.is_file(), f"missing C9 module: {MODULE_PATH}"
    name = "kf_test_semver_pep440"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return load_module()


def test_module_is_stdlib_only() -> None:
    assert MODULE_PATH.is_file(), f"missing C9 module: {MODULE_PATH}"
    source = MODULE_PATH.read_text(encoding="utf-8")
    for third_party in ("hatchling", "packaging", "semver", "typer", "yaml"):
        assert f"import {third_party}" not in source
        assert f"from {third_party}" not in source


def test_api_present(mod: ModuleType) -> None:
    for name in ("parse", "is_semver", "to_pep440"):
        assert callable(getattr(mod, name, None)), f"semver_pep440.{name} missing"


@pytest.mark.parametrize(("semver", "pep440"), VALID)
def test_to_pep440_valid(mod: ModuleType, semver: str, pep440: str) -> None:
    assert mod.to_pep440(semver) == pep440


@pytest.mark.parametrize("bad", INVALID + INVALID_WHITESPACE)
def test_to_pep440_invalid(mod: ModuleType, bad: str) -> None:
    with pytest.raises(ValueError):
        mod.to_pep440(bad)


@pytest.mark.parametrize(("semver", "_pep440"), VALID)
def test_parse_valid_returns_tuple(mod: ModuleType, semver: str, _pep440: str) -> None:
    assert isinstance(mod.parse(semver), tuple)


@pytest.mark.parametrize("bad", INVALID + INVALID_WHITESPACE)
def test_parse_invalid_raises(mod: ModuleType, bad: str) -> None:
    with pytest.raises(ValueError):
        mod.parse(bad)


@pytest.mark.parametrize(("semver", "_pep440"), VALID)
def test_is_semver_true_for_valid(mod: ModuleType, semver: str, _pep440: str) -> None:
    assert mod.is_semver(semver) is True


@pytest.mark.parametrize(
    "bad",
    [
        "01.2.3",
        "1.02.3",
        "1.2.3-rc.01",
        "1.2",
        "1.2.3.4",
        "v1.2.3",
        "1.2.3-",
        "a.b.c",
        *INVALID_WHITESPACE,
    ],
)
def test_is_semver_false_for_non_semver(mod: ModuleType, bad: str) -> None:
    assert mod.is_semver(bad) is False


@pytest.mark.parametrize("value", [v for v, _ in VALID] + INVALID + INVALID_WHITESPACE)
def test_is_semver_never_raises_and_agrees_with_parse(mod: ModuleType, value: str) -> None:
    result = mod.is_semver(value)
    assert isinstance(result, bool)
    try:
        mod.parse(value)
    except ValueError:
        parsed = False
    else:
        parsed = True
    # Anything parse() accepts is SemVer; the converse may not hold (e.g. build metadata).
    if parsed:
        assert result is True
