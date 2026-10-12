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
| T1.0 | Test Engineer | `cli/tests/test_version.py`, `tests/test_layout.py`, `tests/test_check_versions.py`, `tests/test_check_skills_stub.py`, `tests/bats/smoke.bats` | contracts | [x] done (7b5cd51) |
| T1.2+T1.4+S2 [x] 584e84a | CLI Engineer | `cli/**`, `ruff.toml`, `pytest.ini`, layout `.gitkeep`/`__init__.py` (C6 dirs except tests/, .github/), `docs/adr/0001-foundations.md` | T1.0 | [ ] |
| T1.3 [x] 2ff7e79 | Release/CI Engineer | `VERSION`, `CHANGELOG.md`, `CODEOWNERS`, `Makefile`, `.github/workflows/ci.yml`, `tests/check_versions.py`, `tests/check_skills.py` | T1.0 | [ ] |
| S1 [x] f4103d0 | CLI Engineer (spike) | scratch only + `docs/adr/0002-copier-engine.md` | — | [ ] |

Parallel: after T1.0 merges, {T1.2+T1.4+S2, T1.3, S1} run in parallel worktrees (disjoint paths).


## Fix round 1 (after review FAIL — see review.md F1–F10)

Contract amendments (tests are written against these):

C9. **Single version converter** — `cli/semver_pep440.py`, stdlib-only, importable by file path. API:
    `parse(s) -> tuple` / `is_semver(s) -> bool` / `to_pep440(s) -> str` (raises `ValueError` on anything not
    allowed). Allowed: SemVer 2.0 core with NO leading zeros; optional prerelease ONLY in the forms
    `dev` → `.dev0`, `dev.N` → `.devN`, `alpha.N`|`a.N` → `aN`, `beta.N`|`b.N` → `bN`, `rc.N` → `rcN`
    (N without leading zeros). Rejected: build metadata `+…`, bare `rc`/`alpha`/`beta`, any other prerelease,
    whitespace inside. Both `cli/hatch_build.py` and `tests/check_versions.py` MUST use this module (no copies).
    `cli/hatch_build.py` exposes `read_version(root: Path) -> str` (PEP 440) that looks for `VERSION` in `root`
    first (sdist case), then `root.parent` (repo case); hatchling is added to the `dev` group so tests can import it.
C2a. Runtime dependencies list contains `copier` (`>=9.18.2,<10`), `typer`, `pyyaml`, `tomlkit`, `rich`, `jsonschema`.
C3a. `ruff.toml`: `target-version = "py311"`, `line-length = 100`.
C4a. `check_versions.py`: VERSION must be exactly one line (+ optional trailing newline) → else exit 1; JSON file whose
     top level is not an object, or invalid JSON → exit 1 with a one-line message (no traceback).
C5a. `check_skills.py`: SKILL.md frontmatter WITHOUT a `description` key → exit 1.
C7a. `make -n verify` prints the six C7 commands in order; every `uv run` uses `--locked`. CI runs `make verify` on
     Python 3.11 and 3.13 (matrix, via `UV_PYTHON`).
C8a. CHANGELOG: first line `# Changelog`, contains `## [Unreleased]` and at least one `### ` subsection under it.
     CODEOWNERS: contains every PKG §14 rule line (paths adapted to the real layout) with `<org>` placeholders;
     extra rule for `plugins/kuanflow/scripts/` allowed (decision D-P1-2).
C10. `kuanflow` with no arguments prints help; exit code not contracted in P1 (F10 deferred to P4 CLI design).

| ID | Role | Files | Status |
|---|---|---|---|
| FX1.0 | Test Engineer | `cli/tests/test_semver_pep440.py`, `cli/tests/test_hatch_build.py`, `tests/test_tooling_contracts.py`, additions to `tests/test_check_versions.py`, `tests/test_check_skills_stub.py` | [ ] |
| FX1.1 | CLI Engineer | `cli/semver_pep440.py`, `cli/hatch_build.py`, `cli/pyproject.toml` (+hatchling dev), `cli/uv.lock`, `docs/adr/0001-foundations.md` (fix F4) | [ ] |
| FX1.2 | Release/CI | `tests/check_versions.py` (use C9 module, C4a), `tests/check_skills.py` (C5a), `Makefile` (C7a), `.github/workflows/ci.yml` (C7a) | [ ] |

## Verify (phase exit)
`make verify` exit 0; RED run of T1.0 recorded below; ADR-0001/0002 written.

## Evidence log
- RED (T1.0, before implementation): `uvx --with typer --with pyyaml pytest -q cli/tests tests` →
  `70 failed, 6 passed, 1 skipped`; `bats tests/bats` → `not ok 1..3`. 77 pytest + 3 bats tests.

## Decisions log
- D-P1-1: Copier pinned `>=9.18.2,<10` (ADR-0002); synthetic template repo at `.kuanflow/cache/template-repo`.
- D-P1-2: CODEOWNERS adds `plugins/kuanflow/scripts/` (maintainers + security) beyond PKG §14 — guard scripts are as
  sensitive as hooks (PKG §15). To confirm at Gate P1.
- D-P1-3: Coordinator integration commit 5612e3a (copier pin, root `.gitignore`) — integration is the coordinator's
  job; recorded here (review F8).
- D-P1-4: ruff excludes `*.md` from formatting (ruff formats code blocks in Markdown docs we must not edit).

## Status (update before any context reset)
- All P1 tasks merged; GREEN `make verify` exit 0 (77 passed, bats 3/3) at 5612e3a. Review FAIL (6 rows).
- Fix round 1 in progress: FX1.0 tests → FX1.1 ∥ FX1.2.
