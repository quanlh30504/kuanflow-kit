---
work: KF-002-p1-skeleton
phase: P1 — Skeleton & tooling
parent_plan: kuan-workbench/work/KF-001-plan/plan.md
status: in progress
---
# P1 — Skeleton & tooling

## Contracts (shared by Test Engineer and implementers — tests are written against THESE, not against code)

C1. **VERSION** — repo root, one line, SemVer 2.0 (`MAJOR.MINOR.PATCH[-PRERELEASE]`), trailing newline. P1 value: `0.1.0-dev`.

C2. **CLI package** — `cli/pyproject.toml`: name `kuanflow-cli`, `requires-python = ">=3.11"`, build backend hatchling,
    version dynamic from `../VERSION` converted to PEP 440 (`0.1.0-dev` → `0.1.0.dev0`). Entry point
    `kuanflow = "kuanflow_cli.main:app"`. Runtime deps: copier, typer, pyyaml, tomlkit, rich, jsonschema (pinned
    lower bounds). Dev deps (dependency group `dev`): pytest, pytest-cov, ruff.
    `kuanflow --version` prints exactly `kuanflow <pep440-version>` and exits 0.
    `kuanflow_cli.__version__` equals the same PEP 440 string.

C3. **Tool config at repo root** — `ruff.toml` (target py311, line-length 100), `pytest.ini`
    (`testpaths = cli/tests tests`). All commands run from repo root via `uv run --project cli …`.

C4. **`tests/check_versions.py`**
    - `python tests/check_versions.py` → exit 0 when every present version source agrees, else exit 1 with one
      line per mismatch on stderr. Sources: `VERSION` (required; invalid SemVer → exit 1),
      `plugins/kuanflow/.claude-plugin/plugin.json` `.version` (if file exists),
      `.claude-plugin/marketplace.json` `.metadata.version` and the `plugins[name=="kuanflow"].version` (if file exists),
      CLI package version from `cli/pyproject.toml` (dynamic → derived from VERSION; static value → compared after
      SemVer→PEP 440 normalisation).
    - `--tag vX.Y.Z[-pre]` → additionally exit 1 unless tag == `v` + VERSION.
    - `--root <dir>` (default: repo root = parent of `tests/`) so tests can run it on temp trees.

C5. **`tests/check_skills.py <plugin_dir>`** (P1 stub, full rules in P2)
    - Missing argument → exit 2 (usage). Non-existent dir → exit 1.
    - Existing dir: for every `skills/<name>/SKILL.md`, frontmatter must exist with `name == <name>` and non-empty
      `description`; violations → exit 1, one line each on stderr. No skills → exit 0.

C6. **Layout** (PKG §4) — these directories exist (tracked via `.gitkeep` or `__init__.py`):
    `plugins/kuanflow/{.claude-plugin,skills,agents,commands,hooks,scripts}`, `templates/project`,
    `templates/knowledge-repo`, `cli/src/kuanflow_cli/{patchers,adapters,migrations}` (Python packages),
    `evals/{fixtures,trigger,behavior}`, `tests/bats`, `docs/adr`; files `VERSION`, `CHANGELOG.md`, `CODEOWNERS`,
    `Makefile`, `.github/workflows/ci.yml`, `docs/packaging.md`, `docs/playbook.md`.

C7. **`make verify`** runs, stopping at first failure:
    `uv run --project cli ruff check .` · `uv run --project cli ruff format --check .` ·
    `uv run --project cli pytest -q` · `bats tests/bats` ·
    `uv run --project cli python tests/check_skills.py plugins/kuanflow` ·
    `uv run --project cli python tests/check_versions.py`.

C8. **CHANGELOG.md** — Keep a Changelog format, has `## [Unreleased]` section. **CODEOWNERS** — PKG §14 text with
    `<org>` placeholders (no real org).

## Tasks

| ID | Role | Files | Deps | Status |
|---|---|---|---|---|
| T1.1 | Coordinator | docs rename | — | [x] done (commit 0058fac) |
| T1.0 | Test Engineer | `cli/tests/test_version.py`, `tests/test_layout.py`, `tests/test_check_versions.py`, `tests/test_check_skills_stub.py`, `tests/bats/smoke.bats` | contracts | [ ] |
| T1.2+T1.4+S2 | CLI Engineer | `cli/**`, `ruff.toml`, `pytest.ini`, layout `.gitkeep`/`__init__.py` (C6 dirs except tests/, .github/), `docs/adr/0001-foundations.md` | T1.0 | [ ] |
| T1.3 | Release/CI Engineer | `VERSION`, `CHANGELOG.md`, `CODEOWNERS`, `Makefile`, `.github/workflows/ci.yml`, `tests/check_versions.py`, `tests/check_skills.py` | T1.0 | [ ] |
| S1 | CLI Engineer (spike) | scratch only + `docs/adr/0002-copier-engine.md` | — | [ ] |

Parallel: after T1.0 merges, {T1.2+T1.4+S2, T1.3, S1} run in parallel worktrees (disjoint paths).

## Verify (phase exit)
`make verify` exit 0; RED run of T1.0 recorded below; ADR-0001/0002 written.

## Evidence log
(filled during the phase)

## Decisions log

## Status (update before any context reset)
- T1.1 done. Next: T1.0 tests (Test Engineer).
