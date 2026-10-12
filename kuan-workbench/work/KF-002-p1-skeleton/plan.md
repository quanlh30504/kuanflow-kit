---
work: KF-002-p1-skeleton
phase: P1 — Skeleton & tooling
parent_plan: kuan-workbench/work/KF-001-plan/plan.md
status: done — Gate P1 passed (2026-10-12)
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
| T1.2+T1.4+S2 | CLI Engineer | `cli/**`, `ruff.toml`, `pytest.ini`, layout `.gitkeep`/`__init__.py` (C6 dirs except tests/, .github/), `docs/adr/0001-foundations.md` | T1.0 | [x] done (584e84a) |
| T1.3 | Release/CI Engineer | `VERSION`, `CHANGELOG.md`, `CODEOWNERS`, `Makefile`, `.github/workflows/ci.yml`, `tests/check_versions.py`, `tests/check_skills.py` | T1.0 | [x] done (2ff7e79) |
| S1 | CLI Engineer (spike) | scratch only + `docs/adr/0002-copier-engine.md` | — | [x] done (f4103d0) |

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
| FX1.0 | Test Engineer | `cli/tests/test_semver_pep440.py`, `cli/tests/test_hatch_build.py`, `tests/test_tooling_contracts.py`, additions to `tests/test_check_versions.py`, `tests/test_check_skills_stub.py` | [x] done (66c038a); F3/C10 follow-up c903fa0 |
| FX1.1 | CLI Engineer | `cli/semver_pep440.py`, `cli/hatch_build.py`, `cli/pyproject.toml` (+hatchling dev), `cli/uv.lock`, `docs/adr/0001-foundations.md` (fix F4) | [x] done (704c66a) |
| FX1.2 | Release/CI | `tests/check_versions.py` (use C9 module, C4a), `tests/check_skills.py` (C5a), `Makefile` (C7a), `.github/workflows/ci.yml` (C7a) | [x] done (20b1ee4) |

## Gate P1 change R2 — root `pyproject.toml` (user decision 2026-10-12, supersedes ADR-0001 decision 3)

Why: the `cli/`-local project needed ~60 lines of custom build hook (sdist copy, two-place VERSION lookup → F5) and a
`#subdirectory=cli` install URL. A root project uses hatchling's built-in `force-include`; spike evidence in the
ADR-0001 revision. Contract amendments (supersede C2, C3, C7, C9 where they conflict):

C2r. **Project at repo root** — `pyproject.toml` + `uv.lock` at the repo root; `cli/pyproject.toml`, `cli/uv.lock`,
     `cli/hatch_build.py`, `cli/semver_pep440.py` no longer exist. Name, Python floor, backend, entry point, runtime
     deps, dev group (incl. hatchling) as before. Wheel package: `cli/src/kuanflow_cli`. Install form:
     `uvx --from "git+<url>@vX.Y.Z" kuanflow` (no `#subdirectory`).
C7r. All C7 commands run as `uv run --locked <cmd>` from the repo root (no `--project`).
C9r. Converter lives at `cli/src/kuanflow_cli/semver.py` — same API and rules as C9, stdlib-only, imports nothing from
     `kuanflow_cli` (loadable by file path without importing the package). Root `hatch_build.py` holds ONLY a
     metadata hook; `read_version(root)` reads `root/VERSION` only (a `VERSION` in a parent dir is never used) and
     converts via `semver.py`. `tests/check_versions.py` loads the same file; `CLI_PYPROJECT` = `pyproject.toml`.
C11. **Built artefacts** (`python -m hatchling build`): wheel contains `kuanflow_cli/__init__.py`,
     `kuanflow_cli/semver.py`, `kuanflow_cli/_content/plugins/kuanflow/**`, `kuanflow_cli/_content/templates/**`
     and no `tests/`; wheel METADATA `Version` = PEP 440 form of VERSION. sdist contains `VERSION`, `hatch_build.py`,
     `pyproject.toml`, `cli/src/kuanflow_cli/**`, `plugins/kuanflow/**`, `templates/**`. A wheel built from the
     unpacked sdist has the same file list as the wheel built from the repo.

| ID | Role | Files | Status |
|---|---|---|---|
| R2.0 | Test Engineer | `cli/tests/test_semver.py` (renamed), `cli/tests/test_hatch_build.py`, `cli/tests/test_version.py`, `tests/test_tooling_contracts.py`, `tests/test_check_versions.py`, `tests/test_packaging.py` (new) | [x] done (7a6d4bb) |
| R2.1 | CLI Eng | `pyproject.toml`, `uv.lock`, `hatch_build.py`, `cli/src/kuanflow_cli/semver.py`, remove `cli/{pyproject.toml,uv.lock,hatch_build.py,semver_pep440.py,.gitignore}`, ADR-0001 | [ ] |
| R2.2 | Release/CI | `tests/check_versions.py`, `Makefile`, `.github/workflows/ci.yml` (no change needed), `CHANGELOG.md` | [x] done (9bb5283) |

## Verify (phase exit)
`make verify` exit 0; RED run of T1.0 recorded below; ADR-0001/0002 written.

## Evidence log
- GREEN (fix round 1, 20b1ee4): `make verify` exit 0 — `508 passed`, bats `ok 1..3`, both checkers silent.
  Also: pytest on Python 3.11 (`UV_PYTHON=3.11 … --isolated`) → `508 passed`; `uv build` sdist ships
  `semver_pep440.py` + `VERSION`; F5 trap (stray `VERSION=9.9.9` above unpacked sdist) → wheel `0.1.0.dev0`.
  C5a needed no code change (`check_skills.py` already flagged a missing `description` key).
- RED (T1.0, before implementation): `uvx --with typer --with pyyaml pytest -q cli/tests tests` →
  `70 failed, 6 passed, 1 skipped`; `bats tests/bats` → `not ok 1..3`. 77 pytest + 3 bats tests.

## Decisions log
- D-P1-1: Copier pinned `>=9.18.2,<10` (ADR-0002); synthetic template repo at `.kuanflow/cache/template-repo`.
- D-P1-2: CODEOWNERS adds `plugins/kuanflow/scripts/` (maintainers + security) beyond PKG §14 — guard scripts are as
  sensitive as hooks (PKG §15). To confirm at Gate P1.
- D-P1-3: Coordinator integration commit 5612e3a (copier pin, root `.gitignore`) — integration is the coordinator's
  job; recorded here (review F8).
- D-P1-4: ruff excludes `*.md` from formatting (ruff formats code blocks in Markdown docs we must not edit).

## DoD (phase exit)
- [x] `make verify` exit 0 (516 passed, bats 3/3, checkers silent); pytest on Python 3.11 516 passed.
- [x] RED recorded for T1.0, FX1.0, R2.0; GREEN recorded.
- [x] Re-reviews PASS (review.md sections 2 and 3); all high/med findings fixed, lows fixed or answered (Q-28).
- [x] ADR-0001 (decision 3 revised, R2) and ADR-0002 accepted at Gate P1.
- [x] VERSION `0.1.0-dev`; `check_versions.py --tag v0.1.0-dev` exit 0; tag `v0.1.0-dev` (local, not pushed).
- [x] Gate P1: Q-26 → B, Q-27 accepted, Q-28 → A, ADR-0001 + ADR-0002 accepted.

## Status (update before any context reset)
- P1 DONE. Tag `v0.1.0-dev` re-created on the final P1 commit (local only).
- NEXT (on resume): start P2 (KF-003) and P3 (KF-004) per KF-001 plan — create their work folders and contracts,
  tests first. Note for all later tasks: commands are `uv run --locked …` from the repo root (C7r).
