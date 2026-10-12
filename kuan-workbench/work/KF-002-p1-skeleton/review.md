# Review — KF-002 P1 Skeleton & tooling — `82c247c..HEAD` (7b5cd51 … 5612e3a)

Reviewer: Adversarial Reviewer (read-only, 2026-10-12). All experiments ran in a scratch clone
(`/tmp/claude-1000/.../scratchpad/review-p1/c`). Nothing in the repo was changed except this file.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Full verify suite | PASS | `make verify; echo EXIT=$?` → ruff `All checks passed!`, `12 files already formatted`, `77 passed in 1.04s`, bats `ok 1..3`, check_skills and check_versions silent, `EXIT=0`. Also re-ran pytest on Python 3.11.15 (scratch venv): `77 passed`. No test was skipped. |
| 2 | Every contract clause C1–C8 maps to a passing test | **FAIL** | Mapped: C1 → `test_version_file_is_single_semver_line`, bats test 1. C2 name/python/dynamic/entry point/backend → `test_pyproject_metadata`; `--version` → `test_cli_version_in_process`, `test_cli_version_console_script`; `__version__` → `test_package_dunder_version`. C4 → `tests/test_check_versions.py` (11 tests). C5 → `tests/test_check_skills_stub.py` (8 tests). C6 → `tests/test_layout.py`. C8 Unreleased → `test_changelog_has_unreleased_section`. **Unmapped:** C2 runtime deps (copier, typer, pyyaml, tomlkit, rich, jsonschema) and dev group (pytest, pytest-cov, ruff); C3 `ruff.toml` target py311 / line-length 100; C3 `pytest.ini` testpaths (only implicit); C4 "static `[project].version` compared after SemVer→PEP 440 normalisation"; C4 one line per mismatch (only `>= 2`); C5 `description` key absent (only empty string tested); C7 the six commands and their order (bats only greps `bats tests/bats`); C8 CODEOWNERS = PKG §14 text (only `"<org>" in text`); C8 Keep a Changelog format. Mutation results in finding F2. |
| 3 | Weak/tautological tests, skips, tests changed after 7b5cd51 | **FAIL** | `git diff 7b5cd51..HEAD --stat -- tests cli/tests` shows only the two new checker scripts, so no test was modified after the Test Engineer's commit (PASS part). No skips in the green run. But `cli/tests/test_version.py:23-48` tests a SemVer→PEP 440 helper defined **inside the test file**. It never imports `cli/hatch_build.py` or `tests/check_versions.py`, so it would pass even if both real mappings were deleted. 9 of 10 mutations survived in the scratch clone (F2). |
| 4 | Hallucinated APIs (hatchling, typer) | PASS | hatchling 1.32.4 source (uv cache `archive-v0/-TGEJeWyhZDWz9Qb`): `MetadataHookInterface.update(metadata)`, `.root` (`metadata/plugin/interface.py:39,57`); `BuildHookInterface.initialize(version, build_data)`, `.target_name`, `.root` (`builders/hooks/plugin/interface.py:73,111,137`); `build_data.setdefault("force_include", {})` (`builders/plugin/interface.py:432`); wheel versions `standard`/`editable` (`builders/wheel.py:503`). `load_plugin_from_script` picks the single subclass per interface, so one file holding both hooks is valid. Typer: `Typer(no_args_is_help=)`, `Option(..., callback=, is_eager=)`, `typer.Exit`, `typer.testing.CliRunner` all run (`kuanflow --version` → `kuanflow 0.1.0.dev0`, exit 0). |
| 5 | SemVer→PEP 440 mapping consistent in `hatch_build.py` and `check_versions.py` | **FAIL** | The two mappings differ (table in F1). `check_versions.py` accepts `-rc`, `-dev.N`, `-a.N`, `-b.N`, `-alpha`, `-dev.0`. `hatch_build.py` rejects all of them and accepts invalid SemVer with leading zeros (`01.2.3`, `-rc.01`). Scratch clone, `VERSION=1.2.3-rc`: `python3 tests/check_versions.py --tag v1.2.3-rc` → exit 0, while `uv run --project cli …` → `ValueError: VERSION '0.2.0-rc' is not a supported SemVer form`. Build metadata `+x` is rejected by both (consistent). |
| 6 | Scope / extra features / stray TODOs | PASS (with low notes) | Files match role paths, with two exceptions: root `.gitignore`, and the copier pin in `cli/pyproject.toml` + `cli/uv.lock`, both changed by the coordinator commit 5612e3a and outside every role's file list (F8). Extras beyond the docs: `make test/lint/fmt` targets and the CODEOWNERS `scripts/` line (F6). `grep -rn TODO` → only `TODO(verify)` in ADR-0002 and plan text. |
| 7 | Security / hygiene | PASS | No secrets (`grep -iE "password\|secret\|token\|api_key\|PRIVATE"` on the diff: none). Only placeholder URLs (`github.com/<org>/…`, keepachangelog.com, semver.org). Tests use no network: no `requests`/`urllib`/`socket`/remote `git clone`, only subprocesses on `tmp_path`. CI has `permissions: contents: read`, `actions/checkout@v4`, `astral-sh/setup-uv@v5` (major pins). Gaps: no `--locked` (F7); gitleaks (Q-25) is not in the P1 CI skeleton, which is acceptable for the "skeleton running make verify" scope. |
| 8 | Layout vs PKG §4; CODEOWNERS vs PKG §14 | PASS / **FAIL** | Layout: all P1 dirs of PKG §4 exist and are tracked (`.gitkeep` / `__init__.py`); `tests/bats` and `docs/adr` are present. CODEOWNERS adds `plugins/kuanflow/scripts/ @<org>/kuanflow-maintainers @<org>/security`, which is not in PKG §14. C8 says "PKG §14 text" and no Q/ADR records this deviation (F6). |
| 9 | ADRs: evidence, contradictions, TODO(verify) | **FAIL** | ADR-0002 evidence is concrete and consistent with `copier>=9.18.2,<10`, and it lists 4 TODO(verify) items. ADR-0001 contradicts the code: line 142 says `copier>=9.18`, but pyproject has `copier>=9.18.2,<10` (stale after 5612e3a). Line 154 says `check_versions.py` "can rely on the same SemVer -> PEP 440 table", but it implements a different table (F1). Line 27 says "Other pre-release forms are rejected at build time", which is true for the build, but `check_versions` accepts them. `build-system requires hatchling>=1.27` is unverified (only 1.30–1.32 were observed). ADR-0001 has no TODO(verify) items, so its gaps are not flagged. Python ≥3.11 is consistent (ADR, pyproject, uv.lock, ruff). The content locator `parents[3]` is correct for `cli/src/kuanflow_cli/__init__.py`. |
| 10 | Reproducibility from a fresh clone | PASS | `git clone /home/quan3054/kuanflow-kit <scratch>/c && make verify` → `EXIT=0`, `77 passed`, bats `ok 1..3`, tree clean afterwards (`git status --short` empty). VERSION bump `0.2.0-rc.1` → `uv run` rebuilds via `cache-keys` → `kuanflow 0.2.0rc1`, 77 passed. `uv build` → sdist + wheel from sdist, wheel has `kuanflow_cli/_content/{plugins/kuanflow,templates}/…` including a scratch marker file. |
| 11 | "Reject even if green" check | **FAIL** | See section below: the release gate approves versions that cannot be built, and most of C2/C3/C7/C8 is unguarded. |

## Findings

- **F1 — high — `tests/check_versions.py:25-26,37-51` vs `cli/hatch_build.py:21,30-43`: two different SemVer→PEP 440 mappings.**
  `check_versions` is the gate that should prove the CLI package version agrees with VERSION (C4, T1.3, ADR-0001 l.154).
  It approves versions the build backend rejects, and the build backend accepts invalid SemVer that `check_versions` rejects:

  | VERSION | check_versions | hatch_build |
  |---|---|---|
  | `1.2.3-rc` | `1.2.3rc0` | ERR |
  | `0.1.0-dev.2` / `-dev.0` | `0.1.0.dev2` / `.dev0` | ERR |
  | `1.2.3-a.1` / `-b.2` / `-alpha` | `a1` / `b2` / `a0` | ERR |
  | `01.2.3`, `1.02.3`, `1.2.3-rc.01` | ERR | `01.2.3`, `1.02.3`, `1.2.3rc01` |

  Also, `check_cli` returns `[]` for a dynamic version ("consistent by construction", l.119-120), so the mismatch is never surfaced.
  Proof: scratch clone, `printf '1.2.3-rc\n' > VERSION; python3 tests/check_versions.py --tag v1.2.3-rc` → exit 0. In the same tree,
  `uv run --project cli kuanflow --version` → hatchling `ValueError ... not a supported SemVer form`. PKG §18.6 runs
  `python3 tests/check_versions.py` without uv, so a release workflow would pass the version gate and then fail the build.
  Fix: one mapping table shared by both files (or `check_versions` imports/loads `cli/hatch_build.semver_to_pep440`), plus tests that run it on both.
- **F2 — high — tests do not guard large parts of the contract (checklist rows 2, 3).** These mutations in the scratch clone all kept
  `77 passed` and bats `0 not ok`:
  1. Remove `copier` and `jsonschema` from dependencies (C2).
  2. Set ruff `line-length = 120` and `target-version = "py313"` (C3).
  3. Make hatch map `rc.N` to `.postN` (C2 mapping).
  4. Make `check_cli` always return `[]`, which disables the static-version check (C4).
  5. Delete the `ruff check`, `check_skills` and `check_versions` lines from `make verify` (C7).
  6. Replace CODEOWNERS with `* @<org>/x` (C8).
  7. Replace CHANGELOG with a lone `## [Unreleased]` (C8).
  8. Make `check_skills` accept a SKILL.md with no `description` key (C5).

  Only "join all errors on one line" was caught (1 failed). Mutation 5 is the most serious: C7 is the phase exit gate, and it can be
  silently hollowed out while still passing.
- **F3 — med — `cli/tests/test_version.py:23-48`: tautological helper test.** `test_semver_to_pep440_helper` checks a function
  defined in the test file itself. It gives false confidence that the mapping is tested, and the real mappings (F1) have zero direct tests.
- **F4 — med — `docs/adr/0001-foundations.md:142,154`: ADR contradicts the code.**
  - It states `copier>=9.18`, while the code pins `>=9.18.2,<10` (since 5612e3a).
  - It states `check_versions.py` can rely on the same table, which is false (F1).
  - Gate P1 asks the user to accept this ADR, so it must match the code.
  - Proof: `grep -n copier cli/pyproject.toml` vs ADR l.142.
- **F5 — low — `cli/hatch_build.py:46-51` `source_root` prefers `<cli>/..`.** An unpacked sdist whose parent directory contains any
  file named `VERSION` picks up the wrong version root. Proof: `<scratch>/trap/VERSION = 9.9.9`, sdist unpacked in `trap/`,
  `uv build --wheel .` → `FileNotFoundError: Forced include not found: .../trap/templates`. If the parent also had
  `plugins/` and `templates/`, the build would silently produce a wrong version with wrong content. Fix: prefer `<cli>` when
  `<cli>/VERSION` exists (sdist case), or detect the sdist via `PKG-INFO`.
- **F6 — low — `CODEOWNERS:6`: extra `plugins/kuanflow/scripts/` rule not in PKG §14.** C8 requires the PKG §14 text. The
  rule is defensible (guard scripts are security-relevant), but it is an unrecorded deviation. Record it in questions.md or remove it.
- **F7 — low — `Makefile:1` / `.github/workflows/ci.yml:19`: `uv run` without `--locked`.** CI silently re-locks if `pyproject.toml`
  and `uv.lock` diverge, so lockfile drift never fails CI. Also, CI does not pin a Python version, so 3.11 (the declared floor) is
  never exercised in CI (it passes locally: 77 passed on 3.11.15). Fix: `UV_LOCKED=1` (or `--locked`) and a 3.11 matrix entry.
- **F8 — low — process/scope.**
  - Commit 5612e3a (coordinator) edits `cli/pyproject.toml` / `cli/uv.lock` (CLI Engineer's paths) and adds root `.gitignore`. Neither is in any role's file list.
  - In `kuan-workbench/work/KF-002-p1-skeleton/plan.md`, T1.2/T1.3/S1 are still `[ ]`, the GREEN evidence is not logged, and the Decisions log is empty.
- **F9 — low — `tests/check_versions.py`: a few C4 edge cases the contract does not cover.**
  - `read_version` (l.62-70) accepts a multi-line VERSION, though C1 says one line. Only the real file is checked, by pytest.
  - A `plugin.json` / `marketplace.json` whose top level is not an object crashes with a traceback (`_load_json(...).get`) instead of a one-line error. The exit is still 1.
- **F10 — low — `cli/src/kuanflow_cli/main.py:7`: bare `kuanflow` exits 2.** `no_args_is_help=True` makes a bare `kuanflow` print help and exit 2. Not covered by any contract; record it if it is intended.

## "What would make me reject this phase even though verify is green?"

1. **A release gate that approves versions the package cannot build.** Checked: yes (F1). `VERSION=1.2.3-rc` passes
   `check_versions.py --tag v1.2.3-rc` and fails `uv build`. Conversely, `01.2.3` builds but is rejected as SemVer.
   The C4 promise "every version source agrees" is not delivered for the CLI package.
2. **A green suite that stays green when the contract is broken.** Checked: yes (F2). Dropping runtime deps,
   changing the ruff config, removing three of the six `make verify` steps, gutting CODEOWNERS/CHANGELOG, or breaking the
   rc mapping all keep 77/77 + 3/3 green.
3. **ADRs going to Gate P1 that disagree with the code.** Checked: yes (F4).
4. Things I checked that are *not* reasons to reject:
   - the hatchling/typer APIs are real (row 4);
   - a fresh clone reproduces green (row 10);
   - wheel and sdist bundle content correctly;
   - the editable install re-builds on a VERSION bump;
   - there is no network in tests and no secrets.

Required to pass:
- Unify the mapping (F1) and test both real implementations.
- Add tests for C2 deps, C3 config, C7 Makefile steps and order, C8 CODEOWNERS text, C4 static-version normalisation and C5 missing `description` (F2, F3).
- Correct ADR-0001 (F4).

The low findings can be recorded and deferred.

## Verdict: FAIL
