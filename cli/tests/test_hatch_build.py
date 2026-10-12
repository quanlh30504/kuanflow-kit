"""Contract tests C9: cli/hatch_build.py `read_version(root)` delegates to cli/semver_pep440.py."""

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_DIR = REPO_ROOT / "cli"
HATCH_BUILD = CLI_DIR / "hatch_build.py"
SEMVER_MODULE = CLI_DIR / "semver_pep440.py"
TABLES = Path(__file__).resolve().parent / "test_semver_pep440.py"


def _load(path: Path, name: str) -> ModuleType:
    assert path.is_file(), f"missing: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_tables = _load(TABLES, "kf_test_semver_tables_hb")
VALID: list[tuple[str, str]] = _tables.VALID
INVALID: list[str] = _tables.INVALID


@pytest.fixture(scope="module")
def hb() -> ModuleType:
    module = _load(HATCH_BUILD, "kf_test_hatch_build")
    assert callable(getattr(module, "read_version", None)), "hatch_build.read_version missing"
    return module


def write_version(directory: Path, value: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "VERSION").write_text(value + "\n", encoding="utf-8")


def test_version_in_root_wins_over_parent(hb: ModuleType, tmp_path: Path) -> None:
    # sdist case: VERSION is shipped inside the package root; a stray VERSION above must be ignored.
    write_version(tmp_path, "9.9.9")
    root = tmp_path / "kuanflow_cli-1.2.3rc1"
    write_version(root, "1.2.3-rc.1")
    assert hb.read_version(root) == "1.2.3rc1"


def test_falls_back_to_parent(hb: ModuleType, tmp_path: Path) -> None:
    # repo case: root is <repo>/cli, VERSION lives at <repo>/VERSION.
    write_version(tmp_path, "0.1.0-dev")
    root = tmp_path / "cli"
    root.mkdir()
    assert hb.read_version(root) == "0.1.0.dev0"


def test_missing_version_is_error(hb: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "cli"
    root.mkdir()
    with pytest.raises(Exception):  # noqa: B017 - error type not contracted
        hb.read_version(root)


def test_real_repo_version(hb: ModuleType) -> None:
    sem = _load(SEMVER_MODULE, "kf_test_semver_real")
    raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert hb.read_version(CLI_DIR) == sem.to_pep440(raw)


@pytest.mark.parametrize(("semver", "pep440"), VALID)
def test_read_version_valid_table(hb: ModuleType, tmp_path: Path, semver: str, pep440: str) -> None:
    write_version(tmp_path, semver)
    assert hb.read_version(tmp_path) == pep440


@pytest.mark.parametrize("bad", INVALID)
def test_read_version_invalid_table(hb: ModuleType, tmp_path: Path, bad: str) -> None:
    write_version(tmp_path, bad)
    with pytest.raises(ValueError):
        hb.read_version(tmp_path)


def test_source_references_shared_module() -> None:
    assert HATCH_BUILD.is_file()
    assert "semver_pep440" in HATCH_BUILD.read_text(encoding="utf-8")


def test_delegates_to_shared_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy of hatch_build.py next to a fake semver_pep440.py must use the fake converter."""
    work = tmp_path / "cli"
    work.mkdir()
    shutil.copy(HATCH_BUILD, work / "hatch_build.py")
    (work / "semver_pep440.py").write_text(
        "def parse(s):\n"
        "    return (s,)\n"
        "def is_semver(s):\n"
        "    return True\n"
        "def to_pep440(s):\n"
        "    return 'SENTINEL-' + s\n",
        encoding="utf-8",
    )
    write_version(work, "1.2.3-rc.1")
    monkeypatch.syspath_prepend(str(work))
    monkeypatch.delitem(sys.modules, "semver_pep440", raising=False)
    copy = _load(work / "hatch_build.py", "kf_test_hatch_build_copy")
    try:
        assert copy.read_version(work) == "SENTINEL-1.2.3-rc.1"
    finally:
        sys.modules.pop("kf_test_hatch_build_copy", None)
        sys.modules.pop("semver_pep440", None)
