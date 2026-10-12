"""Contract tests C5: tests/check_skills.py (P1 stub)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tests" / "check_skills.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def write_skill(plugin: Path, dirname: str, content: str) -> None:
    d = plugin / "skills" / dirname
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")


def test_missing_argument_is_usage_error() -> None:
    assert run().returncode == 2


def test_nonexistent_dir(tmp_path: Path) -> None:
    assert run(str(tmp_path / "nope")).returncode == 1


def test_empty_plugin_dir(tmp_path: Path) -> None:
    proc = run(str(tmp_path))
    assert proc.returncode == 0, proc.stderr


def test_valid_skill(tmp_path: Path) -> None:
    write_skill(tmp_path, "demo", "---\nname: demo\ndescription: Does a demo thing.\n---\n\nBody\n")
    proc = run(str(tmp_path))
    assert proc.returncode == 0, proc.stderr


def test_name_differs_from_dir(tmp_path: Path) -> None:
    write_skill(tmp_path, "demo", "---\nname: other\ndescription: Does a demo thing.\n---\n")
    proc = run(str(tmp_path))
    assert proc.returncode == 1
    assert proc.stderr.strip()


def test_empty_description(tmp_path: Path) -> None:
    write_skill(tmp_path, "demo", '---\nname: demo\ndescription: ""\n---\n')
    proc = run(str(tmp_path))
    assert proc.returncode == 1
    assert proc.stderr.strip()


def test_missing_frontmatter(tmp_path: Path) -> None:
    write_skill(tmp_path, "demo", "# Demo\n\nNo frontmatter here.\n")
    proc = run(str(tmp_path))
    assert proc.returncode == 1
    assert proc.stderr.strip()


def test_one_line_per_violation(tmp_path: Path) -> None:
    write_skill(tmp_path, "a", "---\nname: wrong\ndescription: x\n---\n")
    write_skill(tmp_path, "b", "no frontmatter\n")
    proc = run(str(tmp_path))
    assert proc.returncode == 1
    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    assert len(lines) >= 2


# --- Fix round 1: C5a ---------------------------------------------------------------------------


def test_missing_description_key(tmp_path: Path) -> None:
    write_skill(tmp_path, "demo", "---\nname: demo\n---\n\nBody\n")
    proc = run(str(tmp_path))
    assert proc.returncode == 1
    assert proc.stderr.strip()
