"""Contract tests C31, C32, C33: the knowledge-repo template and its rendered scripts."""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "knowledge-repo"
COPIER_YML = TEMPLATE / "copier.yml"
CACHE = ".kuanflow/cache/template-repo"

CATEGORIES = [
    "idempotency",
    "concurrency/race",
    "timeout/retry-storm",
    "config",
    "deployment",
    "dependency-external",
    "data-quality",
    "schema/migration",
    "capacity",
    "precision/rounding",
    "time/timezone/calendar",
    "security/auth",
    "observability-gap",
]
SCRIPTS = ["build-index.py", "check-frontmatter.py", "stale-wiki-check.sh"]
TREE = {
    ".copier-answers.yml",
    ".gitignore",
    "README.md",
    "postmortems/README.md",
    "runbooks-shared/README.md",
    "taxonomy.md",
    "templates/postmortem.md",
    "templates/adr.md",
    *(f"scripts/{s}" for s in SCRIPTS),
    ".github/workflows/knowledge-ci.yml",
}

_VI_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯ")
MISSING = object()


def is_english(text: str) -> bool:
    if any(c in _VI_CHARS for c in text):
        return False
    return not any(0x1EA0 <= ord(c) <= 0x1EF9 for c in text)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    assert text.startswith("---\n"), "missing frontmatter"
    end = text.index("\n---\n", 4)
    data = yaml.safe_load(text[4:end])
    assert isinstance(data, dict)
    return data, text[end + 5 :]


def current_version() -> str:
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def kr(tmp_path_factory: pytest.TempPathFactory) -> Path:
    engine = importlib.import_module("kuanflow_cli.engine")
    dst = tmp_path_factory.mktemp("knowledge") / "kr"
    engine.render(dst, {"org_name": "acme"}, template="knowledge-repo")
    return dst


def tree(root: Path) -> set[str]:
    out = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if rel == ".kuanflow/cache" or rel.startswith(".kuanflow/cache/"):
            continue
        if p.is_file() or p.is_symlink():
            out.add(rel)
    return out


# --- C31 copier.yml and rendered tree ---------------------------------------------------------


@pytest.fixture(scope="module")
def copier_yml() -> dict[str, Any]:
    data = yaml.safe_load(COPIER_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_c31_settings(copier_yml: dict[str, Any]) -> None:
    assert copier_yml["_min_copier_version"] == "9.18.2"
    assert copier_yml["_subdirectory"] == "template"
    assert copier_yml["_answers_file"] == ".copier-answers.yml"
    assert copier_yml["_templates_suffix"] == ".jinja"
    for key in ["_tasks", "_migrations", "_jinja_extensions", "_message_after_copy"]:
        assert key not in copier_yml, key
    assert "_copier_conf.src_path" not in COPIER_YML.read_text(encoding="utf-8")


def test_c31_questions(copier_yml: dict[str, Any]) -> None:
    assert {k for k in copier_yml if not k.startswith("_")} == {"org_name", "kuanflow_version"}
    assert copier_yml["org_name"]["type"] == "str"
    assert copier_yml["org_name"]["default"] == "example-org"
    assert copier_yml["kuanflow_version"]["type"] == "str"
    assert copier_yml["kuanflow_version"]["default"] == ""


def test_c31_tree_is_exact(kr: Path) -> None:
    assert tree(kr) == TREE


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    env = {k: v for k, v in env.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=60,
    )
    return proc.stdout


def test_c31a_gitignore(kr: Path) -> None:
    lines = [ln.strip() for ln in (kr / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".kuanflow/cache/" in lines, lines
    assert "index.json" in lines, lines


def test_c31a_cache_ignored_in_fresh_repo(tmp_path: Path) -> None:
    engine = importlib.import_module("kuanflow_cli.engine")
    dst = tmp_path / "kr"
    dst.mkdir()
    _git(dst, "init", "-q", "-b", "main")
    engine.render(dst, {"org_name": "acme"}, template="knowledge-repo")
    assert (dst / CACHE / ".git").is_dir()
    write(dst, "index.json", "{}\n")
    status = _git(dst, "status", "--porcelain", "--untracked-files=all").splitlines()
    paths = [ln[3:] for ln in status]
    assert paths, "rendered files should show as untracked"
    assert not [p for p in paths if p.startswith(".kuanflow/")], paths
    assert "index.json" not in paths, paths
    assert ".gitignore" in paths, paths
    # `git add -A` must not record the cache as an embedded repo (gitlink)
    _git(dst, "add", "-A")
    staged = _git(dst, "ls-files", "--stage").splitlines()
    assert not [ln for ln in staged if ln.startswith("160000")], staged
    assert not [ln for ln in staged if "\t.kuanflow/" in ln], staged


def test_c31_answers_file(kr: Path) -> None:
    ans = yaml.safe_load((kr / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert ans["_src_path"] == CACHE
    assert ans["_commit"] == f"v{current_version()}"
    assert ans["org_name"] == "acme"
    assert ans["kuanflow_version"] == current_version()


@pytest.mark.parametrize("script", SCRIPTS)
def test_c31_scripts_verbatim_and_executable(kr: Path, script: str) -> None:
    src = TEMPLATE / "template" / "scripts" / script
    assert src.is_file(), "scripts are copied verbatim (no .jinja source)"
    assert not (src.parent / f"{script}.jinja").exists()
    got = kr / "scripts" / script
    assert got.read_bytes() == src.read_bytes()
    assert os.access(got, os.X_OK)


def test_c31_rendered_text_is_english(kr: Path) -> None:
    for rel in TREE:
        text = (kr / rel).read_text(encoding="utf-8")
        assert is_english(text), rel


def test_c31_taxonomy_categories(kr: Path) -> None:
    lines = (kr / "taxonomy.md").read_text(encoding="utf-8").splitlines()
    start = lines.index("## Categories")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    cats = []
    for ln in lines[start + 1 : end]:
        m = re.fullmatch(r"- `([^`]+)`\s*", ln)
        if m:
            cats.append(m.group(1))
    assert len(cats) == 13, cats
    assert sorted(cats) == sorted(CATEGORIES)


def test_c31_workflow(kr: Path) -> None:
    data = yaml.safe_load((kr / ".github/workflows/knowledge-ci.yml").read_text(encoding="utf-8"))
    on = data.get("on", data.get(True))  # PyYAML reads a bare `on` key as True
    triggers = set(on) if isinstance(on, (dict, list)) else {on}
    assert {"push", "pull_request"} <= triggers, on
    steps = [s for job in data["jobs"].values() for s in job["steps"]]
    flat = [json.dumps(s).lower() for s in steps]

    def find(needle: str) -> int:
        idx = [i for i, s in enumerate(flat) if needle in s]
        assert idx, f"no step with {needle!r}: {flat}"
        return idx[0]

    order = [
        find("actions/checkout"),
        find("actions/setup-python"),
        find("pip install pyyaml"),
        find("check-frontmatter.py"),
        find("build-index.py"),
    ]
    assert order == sorted(order), order


def test_c31_postmortem_template(kr: Path, tmp_path: Path) -> None:
    text = (kr / "templates" / "postmortem.md").read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    for key in ["id", "title", "date", "severity", "services", "category", "signatures", "status"]:
        assert key in fm, key
    fm["category"] = "idempotency"
    fm["status"] = "draft"
    root = make_root(kr, tmp_path)
    write(root, "postmortems/2026/INC-1.md", "---\n" + yaml.safe_dump(fm) + "---\n" + body)
    proc = run_check(kr, root)
    assert proc.returncode == 0, proc.stderr


def test_c31_adr_template(kr: Path) -> None:
    text = (kr / "templates" / "adr.md").read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    assert {"id", "title", "status", "date", "deciders"} <= set(fm), fm
    assert len([ln for ln in body.splitlines() if ln.startswith("## ")]) == 5


# --- helpers for C32/C33 ----------------------------------------------------------------------


def make_root(kr: Path, tmp_path: Path, *, taxonomy: bool = True) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    if taxonomy:
        shutil.copy(kr / "taxonomy.md", root / "taxonomy.md")
    return root


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def postmortem(date: str | None = "2026-11-03", **over: Any) -> str:
    fm: dict[str, Any] = {
        "id": "INC-0042",
        "title": "Duplicate orders on retry",
        "severity": "SEV2",
        "services": ["order-service", "settlement-service"],
        "category": "idempotency",
        "signatures": ["DuplicateKeyException: order_ref"],
        "status": "approved",
    }
    for k, v in over.items():
        if v is MISSING:
            fm.pop(k, None)
        else:
            fm[k] = v
    head = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True)
    if date is not None:
        head += f"date: {date}\n"  # unquoted: YAML reads it as a date
    return f"---\n{head}---\n## Summary\nText.\n"


def run_script(
    kr: Path, name: str, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(kr / "scripts" / name), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=cwd,
    )


def run_check(kr: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return run_script(kr, "check-frontmatter.py", "--root", str(root))


def problems(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [ln for ln in proc.stderr.splitlines() if ln.strip()]


# --- C32 check-frontmatter.py -----------------------------------------------------------------


def test_c32_valid(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/2026/INC-0042.md", postmortem())
    write(root, "postmortems/INC-0043.md", postmortem(id="INC-0043", status="draft"))
    proc = run_check(kr, root)
    assert proc.returncode == 0, proc.stderr
    assert problems(proc) == []


def test_c32_no_postmortems(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    proc = run_check(kr, root)
    assert proc.returncode == 0, proc.stderr


def test_c32_readme_skipped(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/README.md", "# Postmortems\nNo frontmatter here.\n")
    write(root, "postmortems/2026/README.md", "# 2026\n")
    proc = run_check(kr, root)
    assert proc.returncode == 0, proc.stderr


def test_c32_default_root_is_cwd(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/x.md", postmortem(status="final"))
    proc = run_script(kr, "check-frontmatter.py", cwd=root)
    assert proc.returncode == 1, proc.stderr
    assert problems(proc)[0].startswith("postmortems/x.md: ")


@pytest.mark.parametrize("field", ["id", "services", "category", "signatures", "status"])
def test_c32_missing_field(kr: Path, tmp_path: Path, field: str) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/2026/INC-1.md", postmortem(**{field: MISSING}))
    proc = run_check(kr, root)
    assert proc.returncode == 1, proc.stderr
    errs = problems(proc)
    assert len(errs) == 1, errs
    assert errs[0].startswith("postmortems/2026/INC-1.md: "), errs
    assert field in errs[0].split(": ", 1)[1], errs


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", 42),
        ("id", None),
        ("services", []),
        ("services", "order-service"),
        ("services", [""]),
        ("services", ["a", 3]),
        ("category", "not-a-category"),
        ("category", "Idempotency"),
        ("signatures", []),
        ("signatures", "boom"),
        ("signatures", [1]),
        ("status", "final"),
        ("status", "draft | approved"),
        ("status", "published"),
        ("status", "Approved"),
        ("status", "Draft"),
        ("status", " approved"),
    ],
)
def test_c32_invalid_value(kr: Path, tmp_path: Path, field: str, value: Any) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/INC-1.md", postmortem(**{field: value}))
    proc = run_check(kr, root)
    assert proc.returncode == 1, proc.stderr
    errs = problems(proc)
    assert len(errs) == 1, errs
    assert errs[0].startswith("postmortems/INC-1.md: "), errs
    assert field in errs[0].split(": ", 1)[1], errs


@pytest.mark.parametrize(
    "text",
    [
        "# No frontmatter\n",
        "---\n- a\n- b\n---\nBody\n",
        "---\nid: [unclosed\n---\nBody\n",
        "\n---\nid: INC-1\n---\n",
    ],
)
def test_c32_bad_frontmatter(kr: Path, tmp_path: Path, text: str) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/INC-1.md", text)
    proc = run_check(kr, root)
    assert proc.returncode == 1, proc.stderr
    errs = problems(proc)
    assert errs, "expected a problem line"
    assert all(e.startswith("postmortems/INC-1.md: ") for e in errs), errs


def test_c32_one_line_per_problem(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/a.md", postmortem(id=MISSING, status="final"))
    write(root, "postmortems/b.md", postmortem(category="nope"))
    write(root, "postmortems/c.md", postmortem())
    proc = run_check(kr, root)
    assert proc.returncode == 1
    errs = problems(proc)
    assert len(errs) == 3, errs
    assert sum(e.startswith("postmortems/a.md: ") for e in errs) == 2, errs
    assert sum(e.startswith("postmortems/b.md: ") for e in errs) == 1, errs


def test_c32_taxonomy_from_file(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path, taxonomy=False)
    write(root, "taxonomy.md", "# Taxonomy\n\n## Categories\n\n- `custom-cat`\n- `other`\n")
    write(root, "postmortems/a.md", postmortem(category="custom-cat"))
    assert run_check(kr, root).returncode == 0
    write(root, "postmortems/b.md", postmortem(category="idempotency"))
    proc = run_check(kr, root)
    assert proc.returncode == 1
    assert problems(proc)[0].startswith("postmortems/b.md: ")


def test_c32_taxonomy_missing(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path, taxonomy=False)
    write(root, "postmortems/a.md", postmortem())
    assert run_check(kr, root).returncode == 2


def test_c32_taxonomy_without_categories(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path, taxonomy=False)
    write(root, "taxonomy.md", "# Taxonomy\n\n## Categories\n\nNothing yet.\n")
    write(root, "postmortems/a.md", postmortem())
    assert run_check(kr, root).returncode == 2


# --- C33 build-index.py -----------------------------------------------------------------------


def index(kr: Path, root: Path, *args: str) -> tuple[dict[str, Any], subprocess.CompletedProcess]:
    proc = run_script(kr, "build-index.py", "--root", str(root), *args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout), proc


def test_c33_empty_root(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    data, _ = index(kr, root)
    assert data == {"version": 1, "entries": []}


def test_c33_postmortem_entry(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/2026/INC-0042.md", postmortem())
    data, proc = index(kr, root)
    assert problems(proc) == []
    assert data["version"] == 1
    assert data["entries"] == [
        {
            "kind": "postmortem",
            "path": "postmortems/2026/INC-0042.md",
            "id": "INC-0042",
            "title": "Duplicate orders on retry",
            "date": "2026-11-03",
            "severity": "SEV2",
            "services": ["order-service", "settlement-service"],
            "category": "idempotency",
            "signatures": ["DuplicateKeyException: order_ref"],
            "status": "approved",
        }
    ]


def test_c33_optional_keys_null(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/a.md", postmortem(date=None, title=MISSING, severity=MISSING))
    data, _ = index(kr, root)
    (entry,) = data["entries"]
    assert entry["title"] is None
    assert entry["date"] is None
    assert entry["severity"] is None


def test_c33_runbook_titles(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "runbooks-shared/README.md", "# Shared runbooks\n")
    write(root, "runbooks-shared/a.md", "---\ntitle: From frontmatter\n---\n# Heading\n")
    write(root, "runbooks-shared/b.md", "Intro\n\n# From heading\n\n# Second\n")
    write(root, "runbooks-shared/sub/replay-events.md", "No heading at all.\n")
    data, _ = index(kr, root)
    assert data["entries"] == [
        {"kind": "runbook", "path": "runbooks-shared/a.md", "title": "From frontmatter"},
        {"kind": "runbook", "path": "runbooks-shared/b.md", "title": "From heading"},
        {
            "kind": "runbook",
            "path": "runbooks-shared/sub/replay-events.md",
            "title": "replay-events",
        },
    ]


def test_c33_readme_skipped_and_invalid_warned(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/README.md", "# Postmortems\n")
    write(root, "postmortems/good.md", postmortem())
    write(root, "postmortems/bad1.md", postmortem(status="final"))
    write(root, "postmortems/bad2.md", "# no frontmatter\n")
    data, proc = index(kr, root)
    assert [e["path"] for e in data["entries"]] == ["postmortems/good.md"]
    warnings = problems(proc)
    assert len(warnings) == 2, warnings
    assert any("postmortems/bad1.md" in w for w in warnings), warnings
    assert any("postmortems/bad2.md" in w for w in warnings), warnings


def test_c33_sorted_by_path(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "runbooks-shared/z.md", "# Z\n")
    write(root, "runbooks-shared/a.md", "# A\n")
    write(root, "postmortems/2027/b.md", postmortem(id="B"))
    write(root, "postmortems/2026/c.md", postmortem(id="C"))
    data, _ = index(kr, root)
    paths = [e["path"] for e in data["entries"]]
    assert paths == sorted(paths)
    assert len(paths) == 4


def test_c33_deterministic_and_out_file(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "postmortems/2026/a.md", postmortem(id="A"))
    write(root, "postmortems/b.md", postmortem(id="B", services=["x", "y"]))
    write(root, "runbooks-shared/r.md", "# R\n")
    _, p1 = index(kr, root)
    _, p2 = index(kr, root)
    assert p1.stdout == p2.stdout
    out1, out2 = tmp_path / "i1.json", tmp_path / "i2.json"
    for out in (out1, out2):
        proc = run_script(kr, "build-index.py", "--root", str(root), "--out", str(out))
        assert proc.returncode == 0, proc.stderr
    assert out1.read_bytes() == out2.read_bytes()
    assert json.loads(out1.read_text(encoding="utf-8")) == json.loads(p1.stdout)


def test_c33_default_root_is_cwd(kr: Path, tmp_path: Path) -> None:
    root = make_root(kr, tmp_path)
    write(root, "runbooks-shared/r.md", "# R\n")
    proc = run_script(kr, "build-index.py", cwd=root)
    assert proc.returncode == 0, proc.stderr
    assert [e["path"] for e in json.loads(proc.stdout)["entries"]] == ["runbooks-shared/r.md"]


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_c33_root_not_a_directory(kr: Path, tmp_path: Path, kind: str) -> None:
    target = tmp_path / "x"
    if kind == "file":
        target.write_text("x", encoding="utf-8")
    proc = run_script(kr, "build-index.py", "--root", str(target))
    assert proc.returncode == 2
