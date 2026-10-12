"""Contract tests C2r, C11: root project layout and the built wheel / sdist."""

import importlib.util
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

GONE = ["cli/pyproject.toml", "cli/uv.lock", "cli/hatch_build.py", "cli/semver_pep440.py"]


@pytest.mark.parametrize("rel", ["pyproject.toml", "uv.lock", "hatch_build.py"])
def test_root_project_files(rel: str) -> None:
    assert (REPO_ROOT / rel).is_file(), f"missing {rel}"


@pytest.mark.parametrize("rel", GONE)
def test_old_cli_project_removed(rel: str) -> None:
    assert not (REPO_ROOT / rel).exists(), f"{rel} must not exist (C2r)"


def _hatchling_build(project: Path, out: Path, target: str) -> Path:
    proc = subprocess.run(
        [sys.executable, "-m", "hatchling", "build", "-t", target, "-d", str(out)],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    pattern = "*.whl" if target == "wheel" else "*.tar.gz"
    (artefact,) = out.glob(pattern)
    return artefact


def _wheel_files(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as zf:
        return {n for n in zf.namelist() if ".dist-info/" not in n}


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as zf:
        meta = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
        for line in zf.read(meta).decode("utf-8").splitlines():
            if line.startswith("Version: "):
                return line.removeprefix("Version: ")
    raise AssertionError("no Version in METADATA")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out = tmp_path_factory.mktemp("dist")
    wheel = _hatchling_build(REPO_ROOT, out / "w", "wheel")
    sdist = _hatchling_build(REPO_ROOT, out / "s", "sdist")
    unpacked = out / "unpacked"
    with tarfile.open(sdist) as tf:
        tf.extractall(unpacked, filter="data")
    (sdist_root,) = unpacked.iterdir()
    wheel_from_sdist = _hatchling_build(sdist_root, out / "ws", "wheel")
    return {"wheel": wheel, "sdist": sdist, "wheel_from_sdist": wheel_from_sdist}


def _tracked(prefix: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", prefix], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return [ln for ln in proc.stdout.splitlines() if ln]


def test_wheel_contents(built: dict[str, Path]) -> None:
    files = _wheel_files(built["wheel"])
    assert "kuanflow_cli/__init__.py" in files
    assert "kuanflow_cli/semver.py" in files
    for rel in _tracked("plugins/kuanflow"):
        assert f"kuanflow_cli/_content/{rel}" in files, rel
    for rel in _tracked("templates"):
        assert f"kuanflow_cli/_content/{rel}" in files, rel
    assert not any("/tests/" in f or f.startswith("tests/") for f in files)


def test_wheel_version_is_pep440(built: dict[str, Path]) -> None:
    path = REPO_ROOT / "cli" / "src" / "kuanflow_cli" / "semver.py"
    spec = importlib.util.spec_from_file_location("kf_test_packaging_semver", path)
    assert spec is not None and spec.loader is not None
    semver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(semver)
    raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert _wheel_version(built["wheel"]) == semver.to_pep440(raw)


def test_sdist_contents(built: dict[str, Path]) -> None:
    with tarfile.open(built["sdist"]) as tf:
        names = {n.split("/", 1)[1] for n in tf.getnames() if "/" in n}
    for rel in ["VERSION", "hatch_build.py", "pyproject.toml", "cli/src/kuanflow_cli/semver.py"]:
        assert rel in names, rel
    for rel in _tracked("plugins/kuanflow") + _tracked("templates") + _tracked("cli/src"):
        assert rel in names, rel


def test_wheel_from_sdist_is_identical(built: dict[str, Path]) -> None:
    assert _wheel_files(built["wheel_from_sdist"]) == _wheel_files(built["wheel"])
    assert _wheel_version(built["wheel_from_sdist"]) == _wheel_version(built["wheel"])


# --- C11a (P3): VERSION and template configs ship in the wheel; content_root() finds them -------

C11A_FILES = [
    "kuanflow_cli/_content/VERSION",
    "kuanflow_cli/_content/templates/project/copier.yml",
    "kuanflow_cli/_content/templates/knowledge-repo/copier.yml",
]


@pytest.mark.parametrize("rel", C11A_FILES)
def test_c11a_wheel_ships_content_file(built: dict[str, Path], rel: str) -> None:
    assert rel in _wheel_files(built["wheel"]), rel
    assert rel in _wheel_files(built["wheel_from_sdist"]), rel


def test_c11a_wheel_version_file_matches(built: dict[str, Path]) -> None:
    with zipfile.ZipFile(built["wheel"]) as zf:
        shipped = zf.read("kuanflow_cli/_content/VERSION").decode("utf-8")
    assert shipped.strip() == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_c11a_content_root_in_installed_wheel(built: dict[str, Path], tmp_path: Path) -> None:
    # An unpacked wheel is what a pure-Python install puts in site-packages.
    site = tmp_path / "site"
    with zipfile.ZipFile(built["wheel"]) as zf:
        zf.extractall(site)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from kuanflow_cli import engine; "
        "print(engine.__file__); print(engine.content_root()); print(engine.current_version())"
    )
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code, str(site)],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    engine_file, root, version = proc.stdout.splitlines()
    assert Path(engine_file).resolve().is_relative_to(site.resolve()), engine_file
    assert Path(root).resolve() == (site / "kuanflow_cli" / "_content").resolve()
    assert version == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
