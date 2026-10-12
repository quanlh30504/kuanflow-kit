"""Render engine (C23-C25, ADR-0002): content lookup, synthetic template repo, Copier copy.

Copier only treats a local path as a versioned template when it is a git repo root, so the CLI
assembles one (``assemble_template``) with one commit and tag per Kuanflow version, then renders
from it with ``copier.run_copy``.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import copier

from kuanflow_cli.semver import parse

CACHE_REPO = ".kuanflow/cache/template-repo"

_PKG_DIR = Path(__file__).resolve().parent
_SCRIPTS = Path("plugins/kuanflow/scripts")
_SCRIPTS_DEST = Path("template/.kuanflow/scripts")

# Fixed identity and dates make the synthetic repo reproducible (same inputs -> same SHAs).
_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "kuanflow",
    "GIT_AUTHOR_EMAIL": "kuanflow@localhost",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "kuanflow",
    "GIT_COMMITTER_EMAIL": "kuanflow@localhost",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
}
_PRE_RANK = {"dev": 0, "a": 1, "b": 2, "rc": 3, None: 4}


def content_root() -> Path:
    """Directory holding ``VERSION``, ``templates/`` and ``plugins/kuanflow/`` (wheel or repo)."""
    # Installed wheel: kuanflow_cli/_content; source tree: cli/src/kuanflow_cli -> repo root.
    for root in (_PKG_DIR / "_content", _PKG_DIR.parents[2]):
        if (root / "templates" / "project" / "copier.yml").is_file():
            return root
    raise FileNotFoundError("Kuanflow content (templates/project/copier.yml) not found")


def current_version() -> str:
    """The Kuanflow version (SemVer) of the shipped content."""
    return (content_root() / "VERSION").read_text(encoding="utf-8").strip()


def _order_key(version: str) -> tuple[int, int, int, int, int]:
    major, minor, patch, label, n = parse(version)
    return (major, minor, patch, _PRE_RANK[label], n or 0)


def _git_env() -> dict[str, str]:
    # Drop inherited GIT_* (e.g. GIT_DIR from a hook) and ignore user/system config: no hooks,
    # signing or init templates apply.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {**env, **_GIT_IDENTITY, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repo: Path, *args: str, env: Mapping[str, str]) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    )


def _clear_worktree(repo: Path) -> None:
    for child in repo.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def assemble_template(
    dest: Path | str, versions: Sequence[tuple[str, Path | str]], *, template: str = "project"
) -> Path:
    """Build a git template repo at ``dest`` with one commit + tag ``v<ver>`` per version (C24)."""
    dest = Path(dest)
    versions = [(v, Path(src)) for v, src in versions]
    # Validate everything before touching dest.
    if not versions:
        raise ValueError("at least one version is required")
    keys = [_order_key(v) for v, _ in versions]
    if any(a >= b for a, b in zip(keys, keys[1:], strict=False)):
        raise ValueError(f"versions must be strictly ascending: {[v for v, _ in versions]}")
    for _, src in versions:
        if not (src / "templates" / template / "copier.yml").is_file():
            raise ValueError(f"unknown template {template!r} in {src}")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    env = _git_env()
    _git(dest, "init", "-q", "-b", "main", env=env)
    for version, src in versions:
        _clear_worktree(dest)
        shutil.copytree(src / "templates" / template, dest, dirs_exist_ok=True)
        if template == "project":
            (dest / _SCRIPTS_DEST).mkdir(parents=True, exist_ok=True)
            for script in sorted((src / _SCRIPTS).iterdir()):
                if script.is_file():
                    target = dest / _SCRIPTS_DEST / script.name
                    shutil.copyfile(script, target)
                    target.chmod(0o755)  # D-P3-4: exec bit regardless of source mode
        _git(dest, "add", "-A", env=env)
        _git(
            dest,
            "commit",
            "-q",
            "--no-verify",
            "--allow-empty",
            "-m",
            f"kuanflow v{version}",
            env=env,
        )
        _git(dest, "tag", f"v{version}", env=env)
    return dest


def render(
    dst: Path | str,
    data: Mapping[str, Any],
    *,
    version: str | None = None,
    content: Path | str | None = None,
    template: str = "project",
) -> None:
    """Render ``template`` at ``version`` into ``dst`` via the synthetic repo in the cache (C25)."""
    version = current_version() if version is None else version
    content = content_root() if content is None else Path(content)
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    assemble_template(dst / CACHE_REPO, [(version, content)], template=template)
    answers = dict(data)
    answers.setdefault("kuanflow_version", version)
    # Relative src_path from the project root keeps `_src_path` portable (ADR-0002).
    with contextlib.chdir(dst):
        copier.run_copy(
            CACHE_REPO,
            ".",
            data=answers,
            defaults=True,
            vcs_ref=f"v{version}",
            quiet=True,
            unsafe=False,
        )
