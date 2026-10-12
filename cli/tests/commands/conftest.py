"""Shared helpers for the command tests (T4.1c): fixture repos, isolated env, CLI runner, snapshots.

The CLI is imported lazily (inside helpers), so a missing command fails tests, not collection.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import stat
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[3]
BLOCKS_DIR = REPO_ROOT / "templates" / "project" / "blocks"
BUILD_PY = REPO_ROOT / "cli" / "tests" / "fixtures" / "build.py"

NOW = "2026-11-03T09:00:00+07:00"
NOW_STAMP = "20261103T090000"
LATER = "2026-11-04T10:00:00+07:00"

FIXTURES = ("empty", "maven", "gradle", "monorepo", "speckit")

BEGIN = {
    "html": "<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->",
    "hash": "# kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here)",
}
END = {"html": "<!-- kuanflow:end -->", "hash": "# kuanflow:end"}

# C46 block table: target -> (body template, style, position).
BLOCKS = {
    "AGENTS.md": ("agents.md.jinja", "html", "top"),
    "CLAUDE.md": ("claude.md.jinja", "html", "top"),
    ".gitignore": ("gitignore.jinja", "hash", "bottom"),
    ".github/pull_request_template.md": ("pr-template.md.jinja", "html", "bottom"),
    ".worktreeinclude": ("worktreeinclude.jinja", "hash", "bottom"),
}
ALWAYS_BLOCKS = ("AGENTS.md", "CLAUDE.md", ".gitignore", ".github/pull_request_template.md")

SCRIPTS = ("guard-bash.sh", "guard-protected-paths.sh", "load-config.sh")
# C27 rendered tree of the project template (use_orca false).
PROJECT_RENDERED = {
    ".copier-answers.yml",
    ".kuanflow/config.yaml",
    ".kuanflow/README.md",
    ".kuanflow/templates/.gitkeep",
    *(f".kuanflow/scripts/{s}" for s in SCRIPTS),
    "kuan-workbench/work/.gitkeep",
    "kuan-workbench/wiki/.gitkeep",
    "docs/adr/0000-template.md",
    "docs/runbooks/README.md",
}
# C46: paths matching `_skip_if_exists` of templates/project/copier.yml.
PROJECT_LOCAL_OWNED = {
    "docs/adr/0000-template.md",
    "docs/runbooks/README.md",
    "kuan-workbench/work/.gitkeep",
    "kuan-workbench/wiki/.gitkeep",
    ".kuanflow/templates/.gitkeep",
    "orca.yaml",
}
MERGE_REQUIRED = {".kuanflow/config.yaml"}

# Programs the fake `shutil.which` controls; anything else resolves for real (git, sh, ...).
CONTROLLED_PROGRAMS = frozenset(
    {
        "claude",
        "codex",
        "opencode",
        "kiro-cli",
        "orca",
        "make",
        "mvn",
        "gradle",
        "npm",
        "pnpm",
        "yarn",
        "node",
    }
)

DOCTOR_LINE = re.compile(r"^(OK  |WARN|FAIL) ([a-z]+): (.*)$")
DOCTOR_SUMMARY = re.compile(r"^doctor: (\d+) ok, (\d+) warn, (\d+) fail$", re.M)


# --- modules ----------------------------------------------------------------------------------


def _load_build() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kf_fixture_build", BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE_BUILD = _load_build()


def engine() -> ModuleType:
    return importlib.import_module("kuanflow_cli.engine")


def current_version() -> str:
    return str(engine().current_version())


def build(name: str, dest: Path) -> Path:
    return Path(FIXTURE_BUILD.build(name, dest))


def git(repo: Path, *args: str, check: bool = True) -> str:
    return str(FIXTURE_BUILD.git(repo, *args, check=check))


def commit_all(repo: Path, message: str = "commit") -> None:
    FIXTURE_BUILD.commit_all(repo, message)


# --- environment ------------------------------------------------------------------------------


class FakeWhich:
    """``shutil.which`` replacement: controlled programs resolve only when listed in ``present``."""

    def __init__(self, real: Any, present: Iterable[str] = ()) -> None:
        self.real = real
        self.present = set(present)

    def __call__(self, cmd: Any, *args: Any, **kwargs: Any) -> str | None:
        name = os.path.basename(str(cmd))
        if name in CONTROLLED_PROGRAMS:
            return f"/usr/bin/{name}" if name in self.present else None
        result: str | None = self.real(cmd, *args, **kwargs)
        return result


@contextlib.contextmanager
def cli_env(
    home: Path, *, present: Iterable[str] = (), now: str = NOW
) -> Iterator[pytest.MonkeyPatch]:
    """Isolated env for the whole test: no GIT_*, no user/system git config, fixed identity and
    clock, a private HOME, and a deterministic ``shutil.which`` (detect and doctor use it)."""
    with pytest.MonkeyPatch.context() as mp:
        for key in list(os.environ):
            if key.startswith("GIT_") or key.startswith("KUANFLOW_"):
                mp.delenv(key)
        for key, value in FIXTURE_BUILD.git_env({}).items():
            mp.setenv(key, value)
        home.mkdir(parents=True, exist_ok=True)
        mp.setenv("HOME", str(home))
        mp.delenv("XDG_CONFIG_HOME", raising=False)
        mp.setenv("KUANFLOW_NOW", now)
        real = shutil.which
        while isinstance(real, FakeWhich):
            real = real.real
        mp.setattr(shutil, "which", FakeWhich(real, present))
        yield mp


@pytest.fixture
def env(tmp_path: Path) -> Iterator[pytest.MonkeyPatch]:
    """Function-scoped isolated env (see ``cli_env``); tests may setenv/setattr on it."""
    with cli_env(tmp_path / "_home") as mp:
        yield mp


def set_which(mp: pytest.MonkeyPatch, present: Iterable[str]) -> None:
    real = shutil.which
    while isinstance(real, FakeWhich):
        real = real.real
    mp.setattr(shutil, "which", FakeWhich(real, present))


# --- CLI --------------------------------------------------------------------------------------


def invoke(args: Sequence[str], *, cwd: Path, input: str | None = None) -> Any:
    """Run ``kuanflow <args>`` in-process from ``cwd`` (Typer CliRunner, stdout/stderr apart)."""
    from typer.testing import CliRunner

    app = importlib.import_module("kuanflow_cli.main").app
    with contextlib.chdir(cwd):
        return CliRunner().invoke(app, list(args), input=input)


def describe(result: Any) -> str:
    exc = ""
    if result.exc_info is not None and not isinstance(result.exception, SystemExit):
        import traceback

        exc = "".join(traceback.format_exception(*result.exc_info))
    return (
        f"exit={result.exit_code}\n--- stdout\n{result.stdout}\n--- stderr\n{result.stderr}\n{exc}"
    )


def assert_ok(result: Any) -> None:
    assert result.exit_code == 0, describe(result)


def assert_error(result: Any, *needles: str) -> None:
    """C36a: exit 1, ``error: <message>`` on stderr, no traceback."""
    assert result.exit_code == 1, describe(result)
    assert result.exception is None or isinstance(result.exception, SystemExit), describe(result)
    assert "Traceback" not in result.output, describe(result)
    assert "error: " in result.stderr, describe(result)
    for needle in needles:
        assert needle in result.stderr, f"{needle!r} not in stderr\n{describe(result)}"


def init(root: Path, *extra: str, cwd: Path | None = None) -> Any:
    return invoke(["init", "--yes", *extra], cwd=cwd or root)


def doctor_summary(text: str) -> tuple[int, int, int]:
    m = DOCTOR_SUMMARY.search(text)
    assert m, f"no doctor summary line in:\n{text}"
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def doctor_checks(text: str) -> list[tuple[str, str, str]]:
    """(level, name, message) of each doctor check line in ``text``."""
    out = []
    for line in text.splitlines():
        m = DOCTOR_LINE.match(line)
        if m:
            out.append((m.group(1).strip(), m.group(2), m.group(3)))
    return out


# --- files ------------------------------------------------------------------------------------


def snapshot(top: Path) -> dict[str, tuple[bytes | None, int]]:
    """Every path (files with bytes and mode, dirs as ``None``) outside ``.git/``, plus
    ``.git/info/exclude`` (key ``git:info/exclude``) and ``.git/HEAD``/``.git/config``."""
    out: dict[str, tuple[bytes | None, int]] = {}
    for dirpath, dirnames, filenames in os.walk(top):
        d = Path(dirpath)
        if d == top and ".git" in dirnames:
            dirnames.remove(".git")
        for name in dirnames:
            p = d / name
            out[p.relative_to(top).as_posix() + "/"] = (None, stat.S_IMODE(p.lstat().st_mode))
        for name in filenames:
            p = d / name
            st = p.lstat()
            data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
            out[p.relative_to(top).as_posix()] = (data, stat.S_IMODE(st.st_mode))
    for rel in ("info/exclude", "HEAD", "config"):
        p = top / ".git" / rel
        if p.exists():
            out[f"git:{rel}"] = (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
    return out


def files_under(root: Path, *, skip_cache: bool = True) -> set[str]:
    """Relative posix paths of all files under ``root`` (no ``.git/``, no ``.kuanflow/cache/``)."""
    out = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if skip_cache and (rel == ".kuanflow/cache" or rel.startswith(".kuanflow/cache/")):
            continue
        if p.is_file() or p.is_symlink():
            out.add(rel)
    return out


def write(root: Path, rel: str, text: str | bytes, mode: int | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    if mode is not None:
        p.chmod(mode)
    return p


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def is_exec(p: Path) -> bool:
    return bool(p.stat().st_mode & stat.S_IXUSR)


def read_manifest(root: Path) -> dict[str, Any]:
    data = json.loads((root / ".kuanflow" / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_manifest(root: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (root / ".kuanflow" / "manifest.json").write_text(text, encoding="utf-8")


def manifest_files(root: Path) -> dict[str, dict[str, Any]]:
    return {e["path"]: e for e in read_manifest(root)["files"]}


def read_answers(root: Path) -> dict[str, Any]:
    data = yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def user_answers(root: Path) -> dict[str, Any]:
    return {k: v for k, v in read_answers(root).items() if not k.startswith("_")}


def read_config(root: Path) -> dict[str, Any]:
    data = yaml.safe_load((root / ".kuanflow" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def git_status(top: Path, *extra: str) -> str:
    return git(top, "status", "--porcelain", *extra)


# --- blocks -----------------------------------------------------------------------------------


def normalise_body(body: str) -> str:
    stripped = body.rstrip("\n")
    return stripped + "\n" if stripped else ""


def block_body(target: str, answers: dict[str, Any]) -> str:
    """C46 body for ``target``: the block template rendered with the final answers."""
    name = BLOCKS[target][0]
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    source = (BLOCKS_DIR / name).read_text(encoding="utf-8")
    return normalise_body(env.from_string(source).render(**answers))


def render_block(body: str, style: str) -> str:
    return BEGIN[style] + "\n" + body + END[style] + "\n"


def extract_body(text: str, style: str) -> str | None:
    """The body between the markers (C42 recognition), or ``None`` without a block."""
    lines = text.splitlines(keepends=True)
    begin = end = None
    for i, line in enumerate(lines):
        bare = line.rstrip()
        if begin is None and bare.startswith(BEGIN[style].split(" (")[0]):
            begin = i
        elif begin is not None and bare == END[style]:
            end = i
            break
    if begin is None or end is None:
        return None
    return "".join(lines[begin + 1 : end])


def edit_block_body(path: Path, style: str, new_body: str) -> None:
    text = path.read_text(encoding="utf-8")
    old = extract_body(text, style)
    assert old is not None
    span = BEGIN[style] + "\n" + old + END[style]
    assert span in text
    path.write_text(text.replace(span, BEGIN[style] + "\n" + new_body + END[style]), "utf-8")
