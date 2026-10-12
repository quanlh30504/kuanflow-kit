"""Contract tests C46, C47 (+C40 manifest, C52 fixtures): `kuanflow init` (PKG §12.5, TST-09)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import (
    ALWAYS_BLOCKS,
    BLOCKS,
    FIXTURE_BUILD,
    FIXTURES,
    MERGE_REQUIRED,
    NOW,
    NOW_STAMP,
    PROJECT_LOCAL_OWNED,
    PROJECT_RENDERED,
    assert_error,
    assert_ok,
    block_body,
    build,
    cli_env,
    commit_all,
    current_version,
    describe,
    doctor_checks,
    doctor_summary,
    edit_block_body,
    engine,
    extract_body,
    files_under,
    git,
    init,
    invoke,
    is_exec,
    manifest_files,
    read_answers,
    read_config,
    read_manifest,
    render_block,
    set_which,
    sha256,
    snapshot,
    user_answers,
    write,
    write_manifest,
)

MAVEN_CMDS = {
    "build_cmd": "./mvnw -q -DskipTests package",
    "test_cmd": "./mvnw -q test",
    "verify_cmd": "./mvnw -q verify",
    "single_test_cmd": "./mvnw -q -Dtest={test} test",
    "lint_cmd": "./mvnw -q spotless:check",
}
GRADLE_CMDS = {
    "build_cmd": "./gradlew assemble",
    "test_cmd": "./gradlew test",
    "verify_cmd": "./gradlew check",
    "single_test_cmd": "./gradlew test --tests {test}",
    "lint_cmd": "./gradlew spotlessCheck",
}
MAKE_CMDS = {
    "build_cmd": "make build",
    "test_cmd": "make test",
    "verify_cmd": "make verify",
    "single_test_cmd": "make test TEST={test}",
    "lint_cmd": "make lint",
}
SPECKIT_CMDS = {
    "build_cmd": "make build",  # no scripts.build -> template default
    "test_cmd": "npm test",
    "verify_cmd": "npm test",  # no scripts.verify -> test_cmd
    "single_test_cmd": "npm test -- {test}",
    "lint_cmd": "make lint",
}
MIGRATION = "src/main/resources/db/migration/**"
LEGACY = "**/legacy/**"

EXPECTED_ANSWERS: dict[str, dict[str, Any]] = {
    "empty": {"stack": "other", **MAKE_CMDS, "protected_paths": [LEGACY]},
    "maven": {"stack": "java-maven", **MAVEN_CMDS, "protected_paths": [MIGRATION, LEGACY]},
    "gradle": {"stack": "java-gradle", **GRADLE_CMDS, "protected_paths": [LEGACY]},
    "monorepo": {"stack": "other", **MAKE_CMDS, "protected_paths": [LEGACY]},
    "speckit": {"stack": "node", **SPECKIT_CMDS, "protected_paths": [LEGACY]},
}
# Block targets that existed before init (created == False).
PRE_EXISTING_BLOCKS = {
    "empty": set(),
    "maven": {"CLAUDE.md", ".gitignore"},
    "gradle": set(),
    "monorepo": set(),
    "speckit": {"AGENTS.md"},
}
DETECTED_AGENTS = {
    "empty": "none",
    "maven": "none",
    "gradle": "claude — adapters arrive in a later version",
    "monorepo": "none",
    "speckit": "none",
}


# --- C52 fixture builder sanity (passes before the CLI exists) ---------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_c52_fixture_builder(tmp_path: Path, name: str) -> None:
    root = build(name, tmp_path / name)
    assert git(root, "symbolic-ref", "--short", "HEAD").strip() == "main"
    assert git(root, "status", "--porcelain", "--untracked-files=all") == ""
    tracked = set(git(root, "ls-files").splitlines())
    expected = set(FIXTURE_BUILD.FILES[name])
    assert tracked == expected
    assert files_under(root) == expected
    if name == "empty":
        assert git(root, "rev-list", "--all") == ""
    else:
        assert len(git(root, "rev-list", "--all").split()) == 1
        log = git(root, "log", "-1", "--format=%an <%ae> %aI %cI")
        assert log.strip() == (
            "Fixture Author <fixture@example.com> 2026-01-01T00:00:00+00:00 "
            "2026-01-01T00:00:00+00:00"
        )
    for rel in expected:
        assert is_exec(root / rel) == (rel in FIXTURE_BUILD.EXECUTABLE), rel


def test_c52_fixture_contents(tmp_path: Path) -> None:
    maven = build("maven", tmp_path / "maven")
    paragraphs = [p for p in (maven / "CLAUDE.md").read_text().split("\n\n") if p.strip()]
    assert len(paragraphs) >= 2
    assert (maven / ".gitignore").read_text() == "target/\n*.log\n"
    assert (maven / "src/main/resources/db/migration").is_dir()
    gradle = build("gradle", tmp_path / "gradle")
    text = (gradle / ".claude/settings.json").read_text()
    data = json.loads(text)
    assert data["permissions"]["allow"] and data["permissions"]["deny"]
    assert text == json.dumps(data, indent=2) + "\n"
    mono = build("monorepo", tmp_path / "monorepo")
    scripts = json.loads((mono / "services/web/package.json").read_text())["scripts"]
    assert {"build", "test", "lint"} <= set(scripts)
    assert (mono / "services/web/pnpm-lock.yaml").is_file()
    spec = build("speckit", tmp_path / "speckit")
    assert "test" in json.loads((spec / "package.json").read_text())["scripts"]
    with pytest.raises(ValueError):
        build("nope", tmp_path / "nope")


# --- module-scoped install on each fixture -----------------------------------------------------


@dataclass
class Installed:
    name: str
    root: Path
    before: dict[str, tuple[bytes | None, int]]
    result: Any
    ref_dir: Path

    _ref: Path | None = None

    def reference(self) -> Path:
        """An independent `engine.render` with the answers init recorded."""
        if self._ref is None:
            with cli_env(self.ref_dir / "_home"):
                engine().render(self.ref_dir / "ref", user_answers(self.root))
            self._ref = self.ref_dir / "ref"
        return self._ref


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Installed]:
    out = {}
    for name in FIXTURES:
        base = tmp_path_factory.mktemp(f"init-{name}")
        with cli_env(base / "_home"):
            root = build(name, base / name)
            before = snapshot(root)
            result = init(root)
        out[name] = Installed(name, root, before, result, base)
    return out


@pytest.fixture(params=FIXTURES)
def inst(request: pytest.FixtureRequest, installed: dict[str, Installed]) -> Installed:
    it = installed[request.param]
    assert_ok(it.result)
    return it


def test_c47_init_exit_0_and_doctor_green(inst: Installed) -> None:
    out = inst.result.stdout
    ok, warn, fail = doctor_summary(out)
    assert fail == 0, describe(inst.result)
    assert ok + warn == len(doctor_checks(out))
    assert f"Kuanflow {current_version()} installed (project mode)" in out
    assert "Traceback" not in inst.result.output


def test_c47_init_tree(inst: Installed) -> None:
    pre = {k for k, (data, _) in inst.before.items() if data is not None and ":" not in k}
    expected = pre | PROJECT_RENDERED | set(ALWAYS_BLOCKS) | {".kuanflow/manifest.json"}
    assert files_under(inst.root) == expected
    assert not (inst.root / ".worktreeinclude").exists()  # use_orca false (no orca, no orca.yaml)
    assert not (inst.root / "orca.yaml").exists()


def test_c47_init_rendered_files_match_engine_render(inst: Installed) -> None:
    ref = inst.reference()
    for rel in sorted(PROJECT_RENDERED):
        assert (inst.root / rel).read_bytes() == (ref / rel).read_bytes(), rel
        assert is_exec(inst.root / rel) == is_exec(ref / rel), rel
    for script in (inst.root / ".kuanflow/scripts").iterdir():
        assert is_exec(script), script


def test_c47_init_preexisting_content_untouched(inst: Installed) -> None:
    for rel, (data, mode) in inst.before.items():
        if data is None or rel.startswith("git:") or rel in BLOCKS:
            continue
        p = inst.root / rel
        assert p.read_bytes() == data, rel
        assert p.stat().st_mode & 0o777 == mode, rel


def test_c46_block_bodies_and_positions(inst: Installed) -> None:
    answers = user_answers(inst.root)
    assert answers["kuanflow_version"] == current_version()
    for target in ALWAYS_BLOCKS:
        _, style, position = BLOCKS[target]
        body = block_body(target, answers)
        block = render_block(body, style)
        text = (inst.root / target).read_text(encoding="utf-8")
        assert extract_body(text, style) == body, target
        prior = inst.before.get(target)
        if prior is None:
            assert text == block, target
        else:
            original = prior[0].decode("utf-8") if prior[0] is not None else ""
            if position == "top":
                assert text == block + "\n" + original, target
            else:
                sep = "" if original.endswith("\n") else "\n"
                assert text == original + sep + "\n" + block, target


def test_c46_block_body_values(inst: Installed) -> None:
    gi = extract_body((inst.root / ".gitignore").read_text(encoding="utf-8"), "hash")
    assert gi is not None
    assert ".kuanflow/cache/" in gi.splitlines()
    assert "kuan-workbench/work/*/research.md" in gi.splitlines()  # artifacts_commit minimal
    claude = extract_body((inst.root / "CLAUDE.md").read_text(encoding="utf-8"), "html")
    assert claude == "@AGENTS.md\n"
    pr = extract_body(
        (inst.root / ".github/pull_request_template.md").read_text(encoding="utf-8"), "html"
    )
    assert pr is not None and f"Kuanflow version: v{current_version()}" in pr


def test_c46_maven_claude_and_gitignore_preserved(installed: dict[str, Installed]) -> None:
    it = installed["maven"]
    assert_ok(it.result)
    claude = (it.root / "CLAUDE.md").read_text(encoding="utf-8")
    original = FIXTURE_BUILD.FILES["maven"]["CLAUDE.md"]
    assert claude.endswith("\n" + original)
    assert claude.startswith(
        "<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->\n"
    )
    gitignore = (it.root / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.startswith("target/\n*.log\n\n# kuanflow:begin")
    assert gitignore.endswith("# kuanflow:end\n")


def test_c46_gradle_settings_json_untouched(installed: dict[str, Installed]) -> None:
    it = installed["gradle"]
    assert_ok(it.result)
    assert (it.root / ".claude/settings.json").read_bytes() == it.before[".claude/settings.json"][0]
    assert not (it.root / ".claude/settings.local.json").exists()
    assert {p for p in files_under(it.root) if p.startswith(".claude/")} == {
        ".claude/settings.json"
    }


def test_c46_speckit_content_untouched(installed: dict[str, Installed]) -> None:
    it = installed["speckit"]
    assert_ok(it.result)
    for rel, (data, _) in it.before.items():
        if rel.startswith((".specify/", "specs/")) and data is not None:
            assert (it.root / rel).read_bytes() == data, rel
    agents = (it.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.endswith("\n" + FIXTURE_BUILD.FILES["speckit"]["AGENTS.md"])
    assert agents.index("kuanflow:end") < agents.index("## Project section")


def test_c40_manifest(inst: Installed) -> None:
    raw = (inst.root / ".kuanflow/manifest.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert raw == json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    version = current_version()
    assert list(data) == [
        "manifest_version",
        "kuanflow_version",
        "template",
        "installed_at",
        "mode",
        "agents",
        "source",
        "files",
    ]
    assert data["manifest_version"] == 1
    assert data["kuanflow_version"] == version
    assert data["template"] == "project"
    assert data["installed_at"] == NOW
    assert data["mode"] == "project"
    assert data["agents"] == []
    assert data["source"] == f"git+https://github.com/<org>/kuanflow.git@v{version}"
    paths = [e["path"] for e in data["files"]]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert set(paths) == PROJECT_RENDERED | set(ALWAYS_BLOCKS)
    answers = user_answers(inst.root)
    for entry in data["files"]:
        rel = entry["path"]
        if rel in BLOCKS:
            _, style, _ = BLOCKS[rel]
            assert list(entry) == ["path", "owner", "block", "sha256", "created"], rel
            assert entry["owner"] == "managed-block"
            assert entry["block"] == "kuanflow"
            assert entry["sha256"] == sha256(block_body(rel, answers)), rel
            body = extract_body((inst.root / rel).read_text(encoding="utf-8"), style)
            assert body is not None and entry["sha256"] == sha256(body), rel
            assert entry["created"] is (rel not in PRE_EXISTING_BLOCKS[inst.name]), rel
        else:
            assert list(entry) == ["path", "owner", "sha256"], rel
            if rel in PROJECT_LOCAL_OWNED:
                owner = "local-owned"
            elif rel in MERGE_REQUIRED:
                owner = "merge-required"
            else:
                owner = "template-managed"
            assert entry["owner"] == owner, rel
            assert entry["sha256"] == sha256((inst.root / rel).read_bytes()), rel


def test_c39_detected_answers(inst: Installed) -> None:
    answers = read_answers(inst.root)
    for key, value in EXPECTED_ANSWERS[inst.name].items():
        assert answers[key] == value, key
    assert answers["project_name"] == inst.name
    assert answers["use_orca"] is False
    assert answers["kuanflow_version"] == current_version()
    assert answers["_commit"] == f"v{current_version()}"
    assert answers["_src_path"] == ".kuanflow/cache/template-repo"
    config = read_config(inst.root)
    assert config["commands"]["verify"] == EXPECTED_ANSWERS[inst.name]["verify_cmd"]
    assert config["protected_paths"] == EXPECTED_ANSWERS[inst.name]["protected_paths"]
    assert config["project"]["name"] == inst.name
    assert config["kuanflow"]["min_version"] == current_version()


def test_c47_printed_answers_and_agents(inst: Installed) -> None:
    out = inst.result.stdout
    lines = out.splitlines()
    expected = EXPECTED_ANSWERS[inst.name]
    for key in ("stack", "verify_cmd", "test_cmd"):
        assert f"{key}: {expected[key]}" in lines, key
    assert f"project_name: {inst.name}" in lines
    keys = ["build_cmd", "lint_cmd", "project_name", "stack", "test_cmd", "verify_cmd"]
    positions = [next(i for i, ln in enumerate(lines) if ln.startswith(k + ": ")) for k in keys]
    assert positions == sorted(positions)
    assert f"Detected agents: {DETECTED_AGENTS[inst.name]}" in lines


def test_c47_change_lines(inst: Installed) -> None:
    lines = inst.result.stdout.splitlines()
    for rel in sorted(PROJECT_RENDERED):
        assert f"create {rel}" in lines, rel
    for target in ALWAYS_BLOCKS:
        verb = "update" if target in PRE_EXISTING_BLOCKS[inst.name] else "create"
        assert f"{verb} {target}" in lines, target


def test_c47_detected_agents_listed(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    set_which(env, {"claude", "codex"})
    root = build("empty", tmp_path / "empty")
    result = init(root)
    assert_ok(result)
    assert (
        "Detected agents: claude, codex — adapters arrive in a later version"
        in result.stdout.splitlines()
    )
    assert read_manifest(root)["agents"] == []  # no adapters in P4


def test_c40_manifest_source_env(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    env.setenv("KUANFLOW_SOURCE", "git+https://example.com/kf.git")
    root = build("empty", tmp_path / "empty")
    assert_ok(init(root))
    assert read_manifest(root)["source"] == f"git+https://example.com/kf.git@v{current_version()}"


def test_c47_here_is_accepted(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    assert_ok(invoke(["init", "--here", "--yes"], cwd=root))
    assert (root / ".kuanflow/manifest.json").is_file()


# --- prompt ------------------------------------------------------------------------------------


def test_c47_prompt_no_writes_nothing(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    before = snapshot(root)
    result = invoke(["init"], cwd=root, input="n\n")
    assert result.exit_code == 1, describe(result)
    assert "Apply? [y/N]" in result.output
    assert "verify_cmd: ./mvnw -q verify" in result.stdout
    assert snapshot(root) == before


def test_c47_prompt_empty_answer_is_no(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    before = snapshot(root)
    result = invoke(["init"], cwd=root, input="\n")
    assert result.exit_code == 1, describe(result)
    assert snapshot(root) == before


@pytest.mark.parametrize("answer", ["y", "yes"])
def test_c47_prompt_yes_installs(tmp_path: Path, env: pytest.MonkeyPatch, answer: str) -> None:
    root = build("empty", tmp_path / "empty")
    result = invoke(["init"], cwd=root, input=f"{answer}\n")
    assert_ok(result)
    assert "Apply? [y/N]" in result.output
    assert (root / ".kuanflow/manifest.json").is_file()


# --- --data-file -------------------------------------------------------------------------------


def data_file(tmp_path: Path, content: Any) -> Path:
    p = tmp_path / "answers-data.yml"  # outside the repo: keeps the tree clean
    text = content if isinstance(content, str) else yaml.safe_dump(content, allow_unicode=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_c47_data_file_overrides_detection(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    df = data_file(tmp_path, {"verify_cmd": "make ci", "jira_project_key": "ORD"})
    result = init(root, "--data-file", str(df))
    assert_ok(result)
    answers = read_answers(root)
    assert answers["verify_cmd"] == "make ci"
    assert answers["test_cmd"] == "./mvnw -q test"  # detection still applies to other keys
    assert answers["jira_project_key"] == "ORD"
    assert read_config(root)["commands"]["verify"] == "make ci"
    assert "verify_cmd: make ci" in result.stdout.splitlines()


@pytest.mark.parametrize(
    ("content", "needle"),
    [
        ({"nosuch_question": 1}, "nosuch_question"),
        ({"kuanflow_version": "9.9.9"}, "kuanflow_version"),
        ("- a\n- b\n", None),
        ("key: [unclosed\n", None),
    ],
    ids=["unknown-key", "kuanflow-version", "not-a-mapping", "yaml-error"],
)
def test_c39_bad_data_file(
    tmp_path: Path, env: pytest.MonkeyPatch, content: Any, needle: str | None
) -> None:
    root = build("maven", tmp_path / "maven")
    df = data_file(tmp_path, content)
    before = snapshot(root)
    result = init(root, "--data-file", str(df))
    assert_error(result, *([needle] if needle else []))
    assert df.name in result.stderr
    assert snapshot(root) == before


def test_c39_missing_data_file(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    before = snapshot(root)
    result = init(root, "--data-file", str(tmp_path / "missing.yml"))
    assert_error(result, "missing.yml")
    assert snapshot(root) == before


@pytest.mark.parametrize("value", ["src/**", {"a": "b"}, ["ok/**", 3]])
def test_c46_invalid_list_answer_render_error(
    tmp_path: Path, env: pytest.MonkeyPatch, value: Any
) -> None:
    root = build("maven", tmp_path / "maven")
    df = data_file(tmp_path, {"protected_paths": value})
    before = snapshot(root)
    result = init(root, "--data-file", str(df))
    assert_error(result, "list of strings")
    assert snapshot(root) == before


def test_c47_use_orca_adds_worktreeinclude(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    result = init(root, "--data-file", str(data_file(tmp_path, {"use_orca": True})))
    assert_ok(result)
    body = block_body(".worktreeinclude", user_answers(root))
    assert (root / ".worktreeinclude").read_text(encoding="utf-8") == render_block(body, "hash")
    assert (root / "orca.yaml").is_file()
    files = manifest_files(root)
    assert files[".worktreeinclude"]["owner"] == "managed-block"
    assert files[".worktreeinclude"]["created"] is True
    assert files["orca.yaml"]["owner"] == "local-owned"


def test_c38_orca_on_path_sets_use_orca(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    set_which(env, {"orca"})
    root = build("empty", tmp_path / "empty")
    assert_ok(init(root))
    assert read_answers(root)["use_orca"] is True
    assert (root / ".worktreeinclude").is_file()


# --- refusals (nothing written) ----------------------------------------------------------------


def test_c47_agent_option_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    before = snapshot(root)
    result = init(root, "--agent", "claude")
    assert_error(result, "no agent adapters in this version: claude")
    assert snapshot(root) == before


def test_c47_personal_knowledge_repo_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "empty")
    before = snapshot(root)
    assert_error(init(root, "--personal", "--template", "knowledge-repo"))
    assert snapshot(root) == before


def test_c47_dirty_tree_refused(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, "notes/todo.txt", "wip\n")
    (root / "pom.xml").write_text("<project/>\n")
    before = snapshot(root)
    result = init(root)
    assert_error(result, "notes/todo.txt", "pom.xml")
    assert snapshot(root) == before


def test_c47_ignored_files_do_not_make_tree_dirty(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, "target/app.jar", "jar")
    write(root, "build.log", "log\n")
    assert_ok(init(root))


def test_c47_not_a_git_repo(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    write(plain, "README.md", "hi\n")
    result = init(plain)
    assert_error(result)
    assert sorted(p.name for p in plain.iterdir()) == ["README.md"]


def installed_committed(tmp_path: Path, name: str = "empty") -> Path:
    root = build(name, tmp_path / name)
    assert_ok(init(root))
    commit_all(root, "kuanflow init")
    return root


@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("kuanflow_version", "0.0.1", "kuanflow upgrade"),
        ("mode", "personal", None),
        ("template", "knowledge-repo", None),
    ],
)
def test_c47_existing_manifest_mismatch(
    tmp_path: Path, env: pytest.MonkeyPatch, field: str, value: str, needle: str | None
) -> None:
    root = installed_committed(tmp_path)
    data = read_manifest(root)
    data[field] = value
    write_manifest(root, data)
    commit_all(root, "edit manifest")
    before = snapshot(root)
    result = init(root)
    assert_error(result, *([needle] if needle else []))
    assert snapshot(root) == before


def test_c47_other_template_than_installed(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed_committed(tmp_path)
    before = snapshot(root)
    assert_error(init(root, "--template", "knowledge-repo"))
    assert snapshot(root) == before


# --- conflicts and --force ---------------------------------------------------------------------


def backup_dir(root: Path) -> Path:
    return root / ".kuanflow" / "cache" / "backup" / NOW_STAMP


def test_c47_modified_template_managed_conflict(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed_committed(tmp_path)
    write(root, ".kuanflow/README.md", "my own readme\n")
    write(root, ".kuanflow/scripts/guard-bash.sh", "#!/bin/sh\nexit 0\n", mode=0o755)
    commit_all(root, "edit")
    before = snapshot(root)
    result = init(root)
    assert_error(
        result,
        "modified since install: .kuanflow/README.md",
        "modified since install: .kuanflow/scripts/guard-bash.sh",
    )
    assert snapshot(root) == before


def test_c47_modified_template_managed_force(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed_committed(tmp_path)
    original = (root / ".kuanflow/README.md").read_bytes()
    write(root, ".kuanflow/README.md", "my own readme\n")
    commit_all(root, "edit")
    result = init(root, "--force")
    assert_ok(result)
    assert (root / ".kuanflow/README.md").read_bytes() == original
    assert (backup_dir(root) / ".kuanflow/README.md").read_text() == "my own readme\n"
    assert "update .kuanflow/README.md" in result.stdout.splitlines()
    files = manifest_files(root)
    assert files[".kuanflow/README.md"]["sha256"] == sha256(original)


def test_c47_hand_edited_block_conflict_and_force(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = installed_committed(tmp_path)
    good = (root / "AGENTS.md").read_bytes()
    edit_block_body(root / "AGENTS.md", "html", "## AI workflow\n- my own rule\n")
    commit_all(root, "edit block")
    edited = (root / "AGENTS.md").read_bytes()
    before = snapshot(root)
    assert_error(init(root), "modified since install: AGENTS.md")
    assert snapshot(root) == before
    result = init(root, "--force")
    assert_ok(result)
    assert (root / "AGENTS.md").read_bytes() == good
    assert (backup_dir(root) / "AGENTS.md").read_bytes() == edited


def test_c47_preexisting_differing_file_without_manifest(
    tmp_path: Path, env: pytest.MonkeyPatch
) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, ".kuanflow/README.md", "project notes about kuanflow\n")
    commit_all(root, "pre-existing")
    before = snapshot(root)
    result = init(root)
    assert_error(result, "modified since install: .kuanflow/README.md")
    assert snapshot(root) == before
    assert not (root / ".kuanflow/manifest.json").exists()
    forced = init(root, "--force")
    assert_ok(forced)
    assert (root / ".kuanflow/README.md").read_text() != "project notes about kuanflow\n"
    assert (backup_dir(root) / ".kuanflow/README.md").read_text() == (
        "project notes about kuanflow\n"
    )


def test_c47_broken_block_markers(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    text = (root / "CLAUDE.md").read_text()
    write(root, "CLAUDE.md", "<!-- kuanflow:begin -->\nhalf a block\n" + text)
    commit_all(root, "broken")
    before = snapshot(root)
    assert_error(init(root))  # BlockError
    assert snapshot(root) == before


def test_c47_local_owned_preexisting_skipped(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("maven", tmp_path / "maven")
    write(root, "docs/adr/0000-template.md", "# Our own ADR template\n")
    write(root, "orca.yaml", "worktree:\n  custom: true\n")
    commit_all(root, "project-owned")
    result = init(root)
    assert_ok(result)
    lines = result.stdout.splitlines()
    assert "skip docs/adr/0000-template.md (exists, project-owned)" in lines
    assert "skip orca.yaml (exists, project-owned)" in lines
    assert (root / "docs/adr/0000-template.md").read_text() == "# Our own ADR template\n"
    assert (root / "orca.yaml").read_text() == "worktree:\n  custom: true\n"
    assert read_answers(root)["use_orca"] is True  # orca.yaml exists (DET-06)
    files = manifest_files(root)
    assert "docs/adr/0000-template.md" not in files  # not created by Kuanflow
    assert "orca.yaml" not in files
    assert files["docs/runbooks/README.md"]["owner"] == "local-owned"
    assert files[".worktreeinclude"]["created"] is True


# --- knowledge-repo template -------------------------------------------------------------------


def test_c47_knowledge_repo_init(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "knowledge")
    df = data_file(tmp_path, {"org_name": "acme"})
    result = init(root, "--template", "knowledge-repo", "--data-file", str(df))
    assert_ok(result)
    answers = user_answers(root)
    assert answers["org_name"] == "acme"
    ref = tmp_path / "ref"
    engine().render(ref, answers, template="knowledge-repo")
    rendered = files_under(ref)
    assert files_under(root) == rendered | {".kuanflow/manifest.json"}
    for rel in rendered:
        assert (root / rel).read_bytes() == (ref / rel).read_bytes(), rel
    for target in ALWAYS_BLOCKS:
        if (root / target).exists():
            assert "kuanflow:begin" not in (root / target).read_text(), target
    data = read_manifest(root)
    assert data["template"] == "knowledge-repo"
    assert data["mode"] == "project"
    assert {e["path"] for e in data["files"]} == rendered
    assert all(e["owner"] == "template-managed" for e in data["files"])
    names = [name for _, name, _ in doctor_checks(result.stdout)]
    assert names == ["manifest", "version", "answers"]
    assert doctor_summary(result.stdout)[2] == 0


def test_c47_knowledge_repo_rejects_project_keys(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("empty", tmp_path / "knowledge")
    df = data_file(tmp_path, {"stack": "node"})
    before = snapshot(root)
    assert_error(init(root, "--template", "knowledge-repo", "--data-file", str(df)), "stack")
    assert snapshot(root) == before


def test_c47_knowledge_repo_no_detection(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    root = build("speckit", tmp_path / "speckit")
    assert_ok(init(root, "--template", "knowledge-repo"))
    answers = user_answers(root)
    assert "stack" not in answers and "verify_cmd" not in answers
    agents = FIXTURE_BUILD.FILES["speckit"]["AGENTS.md"].encode()
    assert (root / "AGENTS.md").read_bytes() == agents  # no blocks for knowledge-repo
    assert not (root / "CLAUDE.md").exists()


def test_c47_stdout_has_no_error_prefix_on_success(inst: Installed) -> None:
    assert not re.search(r"^error: ", inst.result.stdout, re.M)
    assert "error: " not in inst.result.stderr
