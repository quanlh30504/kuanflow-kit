"""Fixture repos for the CLI command tests (contract C52, PKG §12.5).

``build(name, dest)`` creates a git repo at ``dest`` (branch ``main``, isolated git env with a fixed
identity and date) and commits every file once (except ``empty``: ``git init`` only).

Loaded by path (``cli/tests/commands/conftest.py``); this directory has no ``__init__.py``.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

NAMES = ("empty", "maven", "gradle", "monorepo", "speckit")

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}

MVNW = '#!/bin/sh\n# Maven wrapper (fixture stub)\nexec mvn "$@"\n'
GRADLEW = '#!/bin/sh\n# Gradle wrapper (fixture stub)\nexec gradle "$@"\n'

POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>{artifact}</artifactId>
  <version>1.0.0-SNAPSHOT</version>
</project>
"""

MAVEN_CLAUDE_MD = """\
# Order service

This service owns the order lifecycle. Keep controllers thin and put the business rules in the
domain package; every money amount is a BigDecimal.

Run `./mvnw -q verify` before pushing. Migrations live in src/main/resources/db/migration and are
never edited after they are merged.
"""

GRADLE_SETTINGS_JSON = """\
{
  "permissions": {
    "allow": [
      "Bash(./gradlew test)",
      "Bash(git status)"
    ],
    "deny": [
      "Read(./secrets/**)",
      "Bash(rm -rf *)"
    ]
  }
}
"""

WEB_PACKAGE_JSON = """\
{
  "name": "web",
  "private": true,
  "scripts": {
    "build": "vite build",
    "test": "vitest run",
    "lint": "eslint ."
  }
}
"""

SPECKIT_PACKAGE_JSON = """\
{
  "name": "speckit-app",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
"""

SPECKIT_AGENTS_MD = """\
# Project guide

## Project section
- This repository uses Spec Kit: specs live in `specs/`, the constitution in `.specify/memory/`.
- Write the spec before the code.
"""

FILES: dict[str, dict[str, str]] = {
    "empty": {},
    "maven": {
        "pom.xml": POM.format(artifact="order-service"),
        "mvnw": MVNW,
        "src/main/java/com/example/App.java": (
            "package com.example;\n\npublic class App {\n"
            "    public static void main(String[] args) {}\n}\n"
        ),
        "src/main/resources/db/migration/V1__init.sql": (
            "CREATE TABLE orders (id BIGINT PRIMARY KEY, amount NUMERIC(19, 4) NOT NULL);\n"
        ),
        "CLAUDE.md": MAVEN_CLAUDE_MD,
        ".gitignore": "target/\n*.log\n",
    },
    "gradle": {
        "build.gradle.kts": 'plugins {\n    java\n}\n\ngroup = "com.example"\n',
        "settings.gradle.kts": 'rootProject.name = "ledger"\n',
        "gradlew": GRADLEW,
        ".claude/settings.json": GRADLE_SETTINGS_JSON,
    },
    "monorepo": {
        "README.md": "# Platform monorepo\n\nServices live in `services/`.\n",
        "services/order-svc/pom.xml": POM.format(artifact="order-svc"),
        "services/order-svc/mvnw": MVNW,
        "services/web/package.json": WEB_PACKAGE_JSON,
        "services/web/pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
    },
    "speckit": {
        ".specify/memory/constitution.md": (
            "# Constitution\n\n1. Specs first.\n2. Tests before merge.\n"
        ),
        ".specify/templates/spec-template.md": (
            "# Feature spec: [FEATURE]\n\n## User scenarios\n\n## Requirements\n"
        ),
        "specs/001-login/spec.md": (
            "# Feature spec: Login\n\n## User scenarios\n- A user signs in with email.\n"
        ),
        "AGENTS.md": SPECKIT_AGENTS_MD,
        "package.json": SPECKIT_PACKAGE_JSON,
    },
}

EXECUTABLE = {"mvnw", "gradlew", "services/order-svc/mvnw"}


def git_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """``base`` (default ``os.environ``) minus ``GIT_*``, no user/system config, fixed identity."""
    src = os.environ if base is None else base
    env = {k: v for k, v in src.items() if not k.startswith("GIT_")}
    return {
        **env,
        **GIT_IDENTITY,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def git(repo: Path | str, *args: str, check: bool = True) -> str:
    """Run git in ``repo`` with the isolated env; return stdout (not stripped)."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=git_env(),
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {proc.stderr}")
    return proc.stdout


def commit_all(repo: Path | str, message: str = "commit") -> None:
    """Stage everything and commit (no hooks, isolated env)."""
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "--allow-empty", "-m", message)


def build(name: str, dest: Path | str) -> Path:
    """Create fixture repo ``name`` at ``dest`` and return ``dest`` (C52)."""
    if name not in FILES:
        raise ValueError(f"unknown fixture {name!r}; expected one of {NAMES}")
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    git(dest, "init", "-q", "-b", "main")
    for rel, text in FILES[name].items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        path.chmod(0o755 if rel in EXECUTABLE else 0o644)
    if name != "empty":
        commit_all(dest, f"fixture: {name}")
    return dest
