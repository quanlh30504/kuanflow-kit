"""Contract tests C9r: root hatch_build.py `read_version(root)` uses kuanflow_cli/semver.py."""

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HATCH_BUILD = REPO_ROOT / "hatch_build.py"
SEMVER_REL = Path("cli/src/kuanflow_cli/semver.py")
TABLES = Path(__file__).resolve().parent / "test_semver.py"


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


def test_reads_version_in_root(hb: ModuleType, tmp_path: Path) -> None:
    write_version(tmp_path, "9.9.9")
    root = tmp_path / "kuanflow_cli-1.2.3rc1"
    write_version(root, "1.2.3-rc.1")
    assert hb.read_version(root) == "1.2.3rc1"


def test_parent_version_is_never_used(hb: ModuleType, tmp_path: Path) -> None:
    # F5 class: an unrelated VERSION above the project root must not be picked up.
    write_version(tmp_path, "9.9.9")
    root = tmp_path / "unpacked"
    root.mkdir()
    with pytest.raises(Exception):  # noqa: B017 - error type not contracted
        hb.read_version(root)


def test_missing_version_is_error(hb: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(Exception):  # noqa: B017 - error type not contracted
        hb.read_version(tmp_path)


def test_real_repo_version(hb: ModuleType) -> None:
    sem = _load(REPO_ROOT / SEMVER_REL, "kf_test_semver_real")
    raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert hb.read_version(REPO_ROOT) == sem.to_pep440(raw)


@pytest.mark.parametrize(("semver", "pep440"), VALID)
def test_read_version_valid_table(hb: ModuleType, tmp_path: Path, semver: str, pep440: str) -> None:
    write_version(tmp_path, semver)
    assert hb.read_version(tmp_path) == pep440


@pytest.mark.parametrize("bad", INVALID)
def test_read_version_invalid_table(hb: ModuleType, tmp_path: Path, bad: str) -> None:
    write_version(tmp_path, bad)
    with pytest.raises(ValueError):
        hb.read_version(tmp_path)


def test_only_metadata_hook() -> None:
    source = HATCH_BUILD.read_text(encoding="utf-8")
    assert "MetadataHookInterface" in source
    assert "BuildHookInterface" not in source, "content bundling must use built-in force-include"


def test_delegates_to_shared_module(tmp_path: Path) -> None:
    """A copy of hatch_build.py in a tree with a fake semver.py must use the fake converter."""
    shutil.copy(HATCH_BUILD, tmp_path / "hatch_build.py")
    fake = tmp_path / SEMVER_REL
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "def parse(s):\n"
        "    return (s,)\n"
        "def is_semver(s):\n"
        "    return True\n"
        "def to_pep440(s):\n"
        "    return 'SENTINEL-' + s\n",
        encoding="utf-8",
    )
    write_version(tmp_path, "1.2.3-rc.1")
    copy = _load(tmp_path / "hatch_build.py", "kf_test_hatch_build_copy")
    try:
        assert copy.read_version(tmp_path) == "SENTINEL-1.2.3-rc.1"
    finally:
        sys.modules.pop("kf_test_hatch_build_copy", None)
