"""Contract test C6: repository layout."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

DIRS = [
    "plugins/kuanflow/.claude-plugin",
    "plugins/kuanflow/skills",
    "plugins/kuanflow/agents",
    "plugins/kuanflow/commands",
    "plugins/kuanflow/hooks",
    "plugins/kuanflow/scripts",
    "templates/project",
    "templates/knowledge-repo",
    "cli/src/kuanflow_cli",
    "cli/src/kuanflow_cli/patchers",
    "cli/src/kuanflow_cli/adapters",
    "cli/src/kuanflow_cli/migrations",
    "evals/fixtures",
    "evals/trigger",
    "evals/behavior",
    "tests/bats",
    "docs/adr",
]

PACKAGES = [
    "cli/src/kuanflow_cli",
    "cli/src/kuanflow_cli/patchers",
    "cli/src/kuanflow_cli/adapters",
    "cli/src/kuanflow_cli/migrations",
]

FILES = [
    "VERSION",
    "CHANGELOG.md",
    "CODEOWNERS",
    "Makefile",
    ".github/workflows/ci.yml",
    "docs/packaging.md",
    "docs/playbook.md",
]


@pytest.mark.parametrize("rel", DIRS)
def test_directory_exists(rel: str) -> None:
    assert (REPO_ROOT / rel).is_dir(), f"missing directory: {rel}"


@pytest.mark.parametrize("rel", PACKAGES)
def test_python_package_has_init(rel: str) -> None:
    assert (REPO_ROOT / rel / "__init__.py").is_file(), f"missing {rel}/__init__.py"


@pytest.mark.parametrize("rel", FILES)
def test_file_exists(rel: str) -> None:
    assert (REPO_ROOT / rel).is_file(), f"missing file: {rel}"


@pytest.mark.parametrize("rel", [d for d in DIRS if d not in PACKAGES])
def test_directory_is_tracked(rel: str) -> None:
    # Empty dirs are not tracked by git; each must hold at least one file (e.g. .gitkeep).
    path = REPO_ROOT / rel
    assert path.is_dir() and any(path.iterdir()), f"directory is empty (add .gitkeep): {rel}"


def test_changelog_has_unreleased_section() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in text


def test_codeowners_uses_placeholder_org() -> None:
    text = (REPO_ROOT / "CODEOWNERS").read_text(encoding="utf-8")
    assert "<org>" in text
