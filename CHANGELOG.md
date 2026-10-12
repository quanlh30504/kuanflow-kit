# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Guard hooks in `plugins/kuanflow/scripts/`: `guard-bash.sh` blocks force/direct pushes to main, commands
  against production clusters and datastores, destructive `rm`/SQL, reading `.env` files (also inside
  `bash -c`/`eval`), and project patterns from `guard.extra_block_patterns`; `guard-protected-paths.sh` blocks
  edits of existing files matching `protected_paths` (new files allowed); `load-config.sh` prints the
  effective config at session start and warns when Kuanflow is older than `kuanflow.min_version`.
  The guards fail open without `python3`/PyYAML and never import modules from the project directory.
- 10 skills (`daily-plan`, `clarify-requirements`, `write-spec`, `research-solution`, `verify-agent-output`,
  `fintech-review`, `debug-incident`, `write-postmortem`, `work-report`, `knowledge-gardening`), 9 subagents
  and 12 commands (`w0-daily` … `w10-capture`, `doctor`). Content reads `commands.*`/`paths.*` from
  `.kuanflow/config.yaml` and stops when a required key is missing.
- `debug-incident/scripts/collect_context.sh`: builds a masked `context.json` (≤ 50 KB) from local log, trace,
  change and metric files; no network.
- `tests/check_skills.py` now also checks agent tools (allowlist, read-only roles), command frontmatter,
  hard-coded build commands and banned patterns (prompt-injection phrases, disabled TLS, downloads).
- Repository skeleton: `plugins/kuanflow/`, `templates/`, `cli/`, `evals/`, `tests/`, `docs/adr/`.
- `kuanflow --version` prints the installed Kuanflow version.
- Single `VERSION` file as the source of truth for the monorepo version.
- `tests/check_versions.py`: verifies `VERSION`, `plugin.json`, `marketplace.json`, the CLI package
  version and (optionally) a release tag all agree.
- `tests/check_skills.py`: checks every skill has frontmatter with a matching `name` and a
  non-empty `description`.
- `make verify` and a GitHub Actions CI workflow that runs it on Python 3.11 and 3.13 for every push
  and pull request; every `uv run` uses `--locked`, so lockfile drift fails the build.
- `kuanflow_cli/semver.py`: the single SemVer -> PEP 440 converter, shared by the package build,
  `tests/check_versions.py` and the CLI, so the release gate only accepts versions the package can build.
- Python project at the repository root: the wheel bundles `plugins/kuanflow` and `templates`, and
  the CLI installs with `uvx --from "git+https://github.com/<org>/kuanflow.git@vX.Y.Z" kuanflow`.
