"""Contract tests C17–C22: plugin content (skills, agents, commands, collector schema, README).

Verbatim samples are read from the source docs (PB = docs/playbook.md, PKG = docs/packaging.md),
so the tests prove the shipped text matches the docs rather than a copy kept in the tests.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugins" / "kuanflow"
PB = (REPO_ROOT / "docs" / "playbook.md").read_text(encoding="utf-8")
PKG = (REPO_ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

SKILLS = {
    "daily-plan": [],
    "clarify-requirements": ["checklists/fintech-questions.md"],
    "write-spec": ["templates/spec.md"],
    "research-solution": [],
    "verify-agent-output": [],
    "fintech-review": [],
    "debug-incident": ["scripts/collect_context.sh", "schemas/context.schema.json"],
    "write-postmortem": ["templates/postmortem.md"],
    "work-report": [],
    "knowledge-gardening": [],
}
AGENTS = [
    "codebase-locator",
    "codebase-analyzer",
    "pattern-finder",
    "test-writer",
    "adversarial-reviewer",
    "rca-timeline",
    "rca-change-correlation",
    "rca-code-path",
    "rca-past-incident",
]
COMMANDS = [
    "w0-daily",
    "w1-clarify",
    "w2-spec",
    "w3-research",
    "w4-plan",
    "w5-implement",
    "w6-test",
    "w7-debug",
    "w8-verify",
    "w9-report",
    "w10-capture",
    "doctor",
]
WORK_FOLDER_SKILLS = [
    "clarify-requirements",
    "write-spec",
    "research-solution",
    "verify-agent-output",
    "debug-incident",
    "write-postmortem",
]
FINTECH_SKILLS = ["clarify-requirements", "write-spec", "verify-agent-output", "fintech-review"]

# PKG §7.1 keys + guard.extra_block_patterns (Q-11); parents are allowed as well.
CONFIG_KEYS = {
    "schema_version",
    "kuanflow.min_version",
    "project.name",
    "project.stack",
    "commands.build",
    "commands.test",
    "commands.verify",
    "commands.single_test",
    "commands.lint",
    "paths.work",
    "paths.wiki",
    "paths.scratch",
    "paths.adr",
    "paths.runbooks",
    "artifacts.commit",
    "work.ticket_pattern",
    "protected_paths",
    "risk.fintech",
    "workflows.enabled",
    "debug.services",
    "debug.budget.max_turns_total",
    "debug.budget.classification",
    "debug.budget.subagent",
    "debug.budget.fix_rounds",
    "debug.allow_prod_log_access",
    "knowledge.repo",
    "integrations.jira_project_key",
    "guard.extra_block_patterns",
}
ALLOWED_KEYS = (
    CONFIG_KEYS
    | {".".join(k.split(".")[:i]) for k in CONFIG_KEYS for i in range(1, k.count(".") + 1)}
    | {"commands.*", "paths.*", "debug.budget.*"}
)
KEY_ROOTS = sorted({k.split(".")[0] for k in CONFIG_KEYS if "." in k})
KEY_RE = re.compile(r"[`<{]((?:" + "|".join(KEY_ROOTS) + r")(?:\.[a-z_*]+)+)")


# --- helpers -----------------------------------------------------------------------------------


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "missing frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    return yaml.safe_load("\n".join(lines[1:end])) or {}, "\n".join(lines[end + 1 :])


def doc_block(doc: str, anchor: str, lang: str = "markdown") -> str:
    """Return the first ```<lang> fenced block after the first line containing `anchor`."""
    start = doc.index(anchor)
    open_ = doc.index(f"```{lang}\n", start) + len(f"```{lang}\n")
    close = doc.index("\n```", open_)
    return doc[open_:close]


def is_subsequence(needles: list[str], hay: list[str]) -> tuple[bool, str]:
    it = iter(hay)
    for n in needles:
        if not any(h == n for h in it):
            return False, n
    return True, ""


def assert_verbatim(sample: str, target: Path, keys: tuple[str, ...]) -> None:
    s_meta, s_body = split_frontmatter(sample)
    t_meta, t_body = split_frontmatter(target.read_text(encoding="utf-8"))
    for k in keys:
        assert t_meta.get(k) == s_meta.get(k), (
            f"{target}: frontmatter {k!r} differs from the doc sample"
        )
    needles = [ln.rstrip() for ln in s_body.splitlines() if ln.strip()]
    hay = [ln.rstrip() for ln in t_body.splitlines()]
    ok, missing = is_subsequence(needles, hay)
    assert ok, f"{target}: doc line missing or out of order: {missing!r}"


def content_files() -> list[Path]:
    out: list[Path] = []
    for sub in ("skills", "agents", "commands"):
        out += [
            p for p in sorted((PLUGIN / sub).rglob("*")) if p.is_file() and p.name != ".gitkeep"
        ]
    return out


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def skill_md(name: str) -> str:
    return read(PLUGIN / "skills" / name / "SKILL.md")


def command_md(name: str) -> str:
    return read(PLUGIN / "commands" / f"{name}.md")


# --- C17 skills --------------------------------------------------------------------------------


def test_c17_exact_skill_set() -> None:
    found = sorted(p.name for p in (PLUGIN / "skills").iterdir() if p.is_dir())
    assert found == sorted(SKILLS)


@pytest.mark.parametrize("name,extras", sorted(SKILLS.items()))
def test_c17_skill_files_exist(name: str, extras: list[str]) -> None:
    for rel in ["SKILL.md", *extras]:
        assert (PLUGIN / "skills" / name / rel).is_file(), f"missing skills/{name}/{rel}"


@pytest.mark.parametrize("name", sorted(SKILLS))
def test_c17a_before_you_start_first(name: str) -> None:
    _, body = split_frontmatter(skill_md(name))
    headings = [ln for ln in body.splitlines() if ln.startswith("## ")]
    assert headings and headings[0].strip() == "## Before you start", headings[:1]
    section = body.split("## Before you start", 1)[1].split("\n## ", 1)[0]
    assert ".kuanflow/config.yaml" in section
    assert ".kuanflow/config.local.yaml" in section
    low = section.lower()
    assert "stop" in low and "ask" in low and "missing" in low


@pytest.mark.parametrize(
    "name,anchor",
    [
        ("verify-agent-output", "### 8.4"),
        ("fintech-review", "### 8.5"),
        ("debug-incident", "### 8.6"),
    ],
)
def test_c17b_verbatim_skill(name: str, anchor: str) -> None:
    assert_verbatim(
        doc_block(PB, anchor), PLUGIN / "skills" / name / "SKILL.md", ("name", "description")
    )


@pytest.mark.parametrize("name", WORK_FOLDER_SKILLS)
def test_c17c_work_item_resolution_order(name: str) -> None:
    text = skill_md(name)
    idx = [text.find(t) for t in ("KUANFLOW_WORK", "work.ticket_pattern", ".kuanflow/state.json")]
    assert all(i >= 0 for i in idx), idx
    assert idx == sorted(idx), "resolution order must be KUANFLOW_WORK -> branch -> state.json"


@pytest.mark.parametrize("name", FINTECH_SKILLS)
def test_c17d_fintech_gating(name: str) -> None:
    assert "risk.fintech" in skill_md(name)


@pytest.mark.parametrize(
    "name,file", [("write-spec", "spec.md"), ("write-postmortem", "postmortem.md")]
)
def test_c17e_project_template_override(name: str, file: str) -> None:
    text = skill_md(name)
    override, own = text.find(f".kuanflow/templates/{file}"), text.find(f"templates/{file}`")
    assert override >= 0, "project override path not mentioned"
    assert own >= 0, "own template not mentioned"


def test_spec_template_shape() -> None:
    text = read(PLUGIN / "skills/write-spec/templates/spec.md")
    meta, body = split_frontmatter(text)
    assert {"ticket", "status", "approved_by"} <= set(meta)
    for needle in (
        "Acceptance criteria",
        "AC-01",
        "Given",
        "Out of scope",
        "Idempotency",
        "Open questions",
    ):
        assert needle in body, needle


def test_postmortem_template_frontmatter() -> None:
    meta, body = split_frontmatter(read(PLUGIN / "skills/write-postmortem/templates/postmortem.md"))
    required = {
        "id", "title", "date", "severity", "services", "category", "signatures", "detection",
        "duration_minutes", "customer_impact", "fix_pr", "regression_test", "related_adr", "status",
    }  # fmt: skip
    assert required <= set(meta), required - set(meta)
    assert "5 whys" in body.lower()


def test_postmortem_skill_lists_taxonomy() -> None:
    line = next(ln for ln in PB.splitlines() if ln.startswith("`idempotency`"))
    categories = re.findall(r"`([^`]+)`", line)
    assert len(categories) == 13
    text = skill_md("write-postmortem")
    for c in categories:
        assert f"`{c}`" in text, c


def test_fintech_questions_checklist() -> None:
    text = read(PLUGIN / "skills/clarify-requirements/checklists/fintech-questions.md").lower()
    for needle in (
        "idempotency",
        "holiday",
        "cut-off",
        "t+n",
        "timezone",
        "rounding",
        "audit",
        "personal data",
    ):
        assert needle in text, needle


# --- C18 agents --------------------------------------------------------------------------------


def test_c18_exact_agent_set() -> None:
    found = sorted(p.stem for p in (PLUGIN / "agents").glob("*.md"))
    assert found == sorted(AGENTS)


@pytest.mark.parametrize("name", ["codebase-analyzer", "test-writer", "adversarial-reviewer"])
def test_c18_verbatim_agent(name: str) -> None:
    sample = doc_block(PB, f"`.claude/agents/{name}.md`")
    assert_verbatim(sample, PLUGIN / "agents" / f"{name}.md", ("name", "description", "tools"))


@pytest.mark.parametrize("name", [a for a in AGENTS if a not in ("test-writer",)])
def test_c18_read_only(name: str) -> None:
    meta, _ = split_frontmatter(read(PLUGIN / "agents" / f"{name}.md"))
    tools = meta["tools"]
    tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else tools
    assert "Write" not in tools and "Edit" not in tools


@pytest.mark.parametrize("name", [a for a in AGENTS if a.startswith("rca-")])
def test_c18_rca_agents_have_budget_and_untrusted_data_rule(name: str) -> None:
    text = read(PLUGIN / "agents" / f"{name}.md").lower()
    assert "turn" in text
    assert "untrusted" in text


# --- C19 commands ------------------------------------------------------------------------------


def test_c19_exact_command_set() -> None:
    found = sorted(p.stem for p in (PLUGIN / "commands").glob("*.md"))
    assert found == sorted(COMMANDS)


@pytest.mark.parametrize("name", COMMANDS)
def test_c19_command_frontmatter_and_arguments(name: str) -> None:
    meta, body = split_frontmatter(command_md(name))
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    assert isinstance(meta.get("argument-hint"), str) and meta["argument-hint"].strip()
    assert "$ARGUMENTS" in body


def test_c19_w8_verbatim() -> None:
    sample = doc_block(PKG, "### 5.4")
    assert_verbatim(sample, PLUGIN / "commands" / "w8-verify.md", ("description", "argument-hint"))


@pytest.mark.parametrize("name", [c for c in COMMANDS if c.startswith("w")])
def test_c19_workflow_enabled_gate(name: str) -> None:
    text = command_md(name)
    wid = name.split("-")[0]
    assert "workflows.enabled" in text
    assert f"`{wid}`" in text


@pytest.mark.parametrize(
    "name,targets",
    [
        ("w0-daily", ["daily-plan"]),
        ("w1-clarify", ["clarify-requirements"]),
        ("w2-spec", ["write-spec"]),
        ("w3-research", ["research-solution"]),
        ("w6-test", ["test-writer"]),
        ("w7-debug", ["debug-incident"]),
        ("w8-verify", ["verify-agent-output", "fintech-review"]),
        ("w9-report", ["work-report"]),
        ("w10-capture", ["write-postmortem", "knowledge-gardening"]),
    ],
)
def test_c19_delegation(name: str, targets: list[str]) -> None:
    text = command_md(name)
    for t in targets:
        assert t in text, t


@pytest.mark.parametrize(
    "name,superpowers",
    [
        ("w4-plan", ["writing-plans"]),
        ("w5-implement", ["executing-plans", "test-driven-development"]),
        ("w6-test", ["test-driven-development"]),
        ("w10-capture", ["writing-skills"]),
    ],
)
def test_c19_superpowers_optional(name: str, superpowers: list[str]) -> None:
    text = command_md(name)
    assert "Superpowers" in text
    assert re.search(r"if .{0,80}installed", text, re.IGNORECASE | re.DOTALL)
    for s in superpowers:
        assert f"`{s}`" in text, s


def test_c19_w4_self_contained() -> None:
    text = command_md("w4-plan")
    for needle in (
        "## Phase",
        "Verify:",
        "[ ] todo",
        "[~] doing",
        "[x] done",
        "Stop & ask if",
        "Decisions log",
    ):
        assert needle in text, needle


def test_c19_w5_self_contained() -> None:
    text = command_md("w5-implement").lower()
    assert "existing tests" in text and "skip" in text and "delete" in text
    assert "commands.verify" in text and "plan.md" in text


def test_c19_w6_self_contained() -> None:
    text = command_md("w6-test").lower()
    assert "every ac" in text
    for needle in ("boundar", "idempotency key", "concurren", "tautolog"):
        assert needle in text, needle


def test_c19_w10_self_contained() -> None:
    text = command_md("w10-capture")
    assert any(ln.startswith("|") for ln in text.splitlines())
    for needle in ("postmortem", "runbook", "ADR", "wiki", "checklist", "promote"):
        assert needle in text, needle


def test_c19_doctor() -> None:
    text = command_md("doctor")
    for needle in (
        "kuanflow doctor",
        "PATH",
        "PyYAML",
        "min_version",
        "commands.verify",
        "executable",
    ):
        assert needle in text, needle


# --- C20 no hard-coded project paths, known config keys ----------------------------------------


@pytest.mark.parametrize("path", content_files(), ids=lambda p: str(p.relative_to(PLUGIN)))
def test_c20_no_hard_coded_paths(path: Path) -> None:
    if path.suffix not in (".md", ".json", ".sh"):
        return
    text = read(path)
    for literal in ("kuan-workbench/", "docs/adr", "docs/runbooks"):
        assert literal not in text, f"{literal!r} in {path} (use paths.*)"


def used_keys() -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {}
    for p in content_files():
        if p.suffix != ".md":
            continue
        for k in KEY_RE.findall(read(p)):
            keys.setdefault(k.rstrip("."), []).append(str(p.relative_to(PLUGIN)))
    return keys


def test_c20_keys_exist() -> None:
    keys = used_keys()
    assert keys, "no config keys found in content"
    unknown = {k: v for k, v in keys.items() if k not in ALLOWED_KEYS}
    assert not unknown, unknown


# --- C21 collector schema ----------------------------------------------------------------------

SCHEMA_PATH = PLUGIN / "skills/debug-incident/schemas/context.schema.json"
COLLECT = PLUGIN / "skills/debug-incident/scripts/collect_context.sh"


@pytest.fixture(scope="module")
def schema() -> dict:
    s = json.loads(read(SCHEMA_PATH))
    jsonschema.Draft202012Validator.check_schema(s)
    return s


def test_c21_schema_dialect(schema: dict) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_c21_pb_sample_validates(schema: dict) -> None:
    sample = json.loads(doc_block(PB, "### 6.5", "json"))
    jsonschema.validate(sample, schema, cls=jsonschema.Draft202012Validator)


@pytest.mark.parametrize("drop", ["incident_id", "services", "symptom", "redaction"])
def test_c21_schema_requires_core_fields(schema: dict, drop: str) -> None:
    sample = json.loads(doc_block(PB, "### 6.5", "json"))
    del sample[drop]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(sample, schema, cls=jsonschema.Draft202012Validator)


def test_c21_collector_output_validates(schema: dict, tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / ".kuanflow").mkdir(parents=True)
    log = tmp_path / "app.log"
    log.write_text(
        "2026-11-03 09:12:04.180 ERROR svc DuplicateKeyException: order_ref user=a@b.example.com\n"
        "2026-11-03 09:12:05.000 INFO svc ok\n",
        encoding="utf-8",
    )
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps(
            [
                {
                    "trace_id": "t1",
                    "timeline": [{"t": "09:12:01", "svc": "svc", "event": "POST /x"}],
                    "stack_trace_top": ["A.b:1"],
                }
            ]  # fmt: skip
        ),
        encoding="utf-8",
    )
    changes = tmp_path / "changes.json"
    changes.write_text(json.dumps({"window": ["a", "b"], "deploys": [], "config": [], "flags": []}))
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"error_rate": {"before": 0.001, "after": 0.07}}))
    proc = subprocess.run(
        [
            str(COLLECT),
            "--id",
            "INC-1",
            "--root",
            str(root),
            "--service",
            "svc",
            "--log",
            str(log),
            "--trace",
            str(trace),
            "--changes",
            str(changes),
            "--metrics",
            str(metrics),
            "--symptom",
            "errors",
            "--severity",
            "SEV2",
            "--source",
            "alert",
            "--similar",
            "INC-0042",
        ],  # fmt: skip
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((root / ".kuanflow/scratch/INC-1/context.json").read_text(encoding="utf-8"))
    jsonschema.validate(out, schema, cls=jsonschema.Draft202012Validator)
    assert out["similar_incidents"] == ["INC-0042"]
    assert out["metrics"]["error_rate"]["after"] == 0.07


# --- C12 executables ---------------------------------------------------------------------------

EXECUTABLES = [
    "scripts/load-config.sh",
    "scripts/guard-bash.sh",
    "scripts/guard-protected-paths.sh",
    "skills/debug-incident/scripts/collect_context.sh",
]


@pytest.mark.parametrize("rel", EXECUTABLES)
def test_c12_executable_in_git(rel: str) -> None:
    path = PLUGIN / rel
    assert os.access(path, os.X_OK), f"not executable: {rel}"
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.startswith("100755 "), f"git mode is not 100755 for {rel}: {out!r}"


@pytest.mark.parametrize("rel", EXECUTABLES)
def test_c12_bash_shebang(rel: str) -> None:
    assert read(PLUGIN / rel).startswith("#!/usr/bin/env bash\n")


# --- C22 README --------------------------------------------------------------------------------


def test_c22_readme_lists_everything() -> None:
    text = read(PLUGIN / "README.md")
    for name in [*SKILLS, *AGENTS, *COMMANDS]:
        assert f"`{name}`" in text, name


def test_c22_readme_key_table_covers_used_keys() -> None:
    text = read(PLUGIN / "README.md")
    missing = sorted(k for k in used_keys() if f"`{k}`" not in text)
    assert not missing, missing
