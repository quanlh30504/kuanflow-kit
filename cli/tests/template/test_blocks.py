"""Contract tests C30: patcher block bodies in templates/project/blocks/*.jinja."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[3]
BLOCKS = REPO_ROOT / "templates" / "project" / "blocks"
PKG = REPO_ROOT / "docs" / "packaging.md"
ANSWERS_DIR = REPO_ROOT / "tests" / "answers"

NAMES = ["agents.md", "claude.md", "gitignore", "pr-template.md", "worktreeinclude"]

Q16_LINE = "- No slash commands in your agent? Run the `verify-agent-output` skill (W8) instead."

ENGINE_LINES = [
    ".kuanflow/config.local.yaml",
    ".kuanflow/state.json",
    ".kuanflow/scratch/",
    ".kuanflow/cache/",
]
MODE_LINES = {
    "minimal": [
        "kuan-workbench/work/*/questions.md",
        "kuan-workbench/work/*/research.md",
        "kuan-workbench/work/*/options.md",
    ],
    "none": ["kuan-workbench/"],
    "full": [],
}


@pytest.fixture(scope="module")
def answers(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    engine = importlib.import_module("kuanflow_cli.engine")
    dst = tmp_path_factory.mktemp("blocks") / "proj"
    data = yaml.safe_load((ANSWERS_DIR / "java-maven.yml").read_text(encoding="utf-8"))
    engine.render(dst, data)
    ans = yaml.safe_load((dst / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert isinstance(ans, dict)
    return ans


def source(name: str) -> str:
    return (BLOCKS / f"{name}.jinja").read_text(encoding="utf-8")


def render_block(name: str, answers: dict[str, Any]) -> str:
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    return env.from_string(source(name)).render(**answers)


def pkg_agents_lines() -> list[str]:
    lines = PKG.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("<!-- kuanflow:begin"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "<!-- kuanflow:end -->")
    body = lines[start + 1 : end]
    assert body, "PKG §6.5 block is empty"
    return body


def test_block_file_set() -> None:
    assert sorted(p.name for p in BLOCKS.iterdir()) == sorted(f"{n}.jinja" for n in NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_block_renders_and_ends_with_one_newline(answers: dict[str, Any], name: str) -> None:
    text = render_block(name, answers)
    assert text.endswith("\n"), repr(text[-20:])
    assert not text.endswith("\n\n"), repr(text[-20:])


@pytest.mark.parametrize("name", NAMES)
def test_block_has_no_markers(answers: dict[str, Any], name: str) -> None:
    for text in (source(name), render_block(name, answers)):
        assert "kuanflow:begin" not in text
        assert "kuanflow:end" not in text


def test_agents_md(answers: dict[str, Any]) -> None:
    got = render_block("agents.md", answers).splitlines()
    pkg = pkg_agents_lines()
    assert got.count(Q16_LINE) == 1, got
    assert len(got) == len(pkg) + 1, got
    assert [ln for ln in got if ln != Q16_LINE] == pkg


def test_claude_md(answers: dict[str, Any]) -> None:
    assert render_block("claude.md", answers) == "@AGENTS.md\n"


@pytest.mark.parametrize("mode", ["minimal", "full", "none"])
def test_gitignore_per_mode(answers: dict[str, Any], mode: str) -> None:
    lines = render_block("gitignore", {**answers, "artifacts_commit": mode}).splitlines()
    engine_comment = "# Kuanflow — engine"
    output_comment = f"# Kuanflow — output (artifacts.commit = {mode})"
    assert lines.count(engine_comment) == 1, lines
    assert lines.count(output_comment) == 1, lines
    entries = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    expected = ENGINE_LINES + ["CLAUDE.local.md"] + MODE_LINES[mode]
    assert sorted(entries) == sorted(expected), entries
    e, o = lines.index(engine_comment), lines.index(output_comment)
    for ln in ENGINE_LINES:
        assert e < lines.index(ln) < o, ln
    for ln in MODE_LINES[mode]:
        assert lines.index(ln) > o, ln


def test_gitignore_default_answers_are_minimal(answers: dict[str, Any]) -> None:
    lines = render_block("gitignore", answers).splitlines()
    assert "# Kuanflow — output (artifacts.commit = minimal)" in lines
    for ln in MODE_LINES["minimal"]:
        assert ln in lines


def test_pr_template(answers: dict[str, Any]) -> None:
    expected = (
        "## AI involvement\n"
        "- [ ] No AI used\n"
        "- [ ] AI assisted (suggestions, review)\n"
        "- [ ] AI wrote most of the code — passed W8\n"
        "\n"
        "Artifacts: `kuan-workbench/work/<TICKET>-<slug>/plan.md` · `review.md`\n"
        f"Kuanflow version: v{answers['kuanflow_version']}\n"
        "\n"
        "## Verify evidence\n"
        "<!-- paste the verify command and its output, or a CI link -->\n"
    )
    assert render_block("pr-template.md", answers) == expected


def test_pr_template_uses_kuanflow_version(answers: dict[str, Any]) -> None:
    text = render_block("pr-template.md", {**answers, "kuanflow_version": "7.8.9"})
    assert "Kuanflow version: v7.8.9\n" in text


def test_worktreeinclude(answers: dict[str, Any]) -> None:
    lines = render_block("worktreeinclude", answers).splitlines()
    entries = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    assert entries == [".kuanflow/config.local.yaml", "CLAUDE.local.md", ".env.local"]
