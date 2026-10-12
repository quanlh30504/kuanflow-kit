# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository skeleton: `plugins/kuanflow/`, `templates/`, `cli/`, `evals/`, `tests/`, `docs/adr/`.
- `kuanflow --version` prints the installed Kuanflow version.
- Single `VERSION` file as the source of truth for the monorepo version.
- `tests/check_versions.py`: verifies `VERSION`, `plugin.json`, `marketplace.json`, the CLI package
  version and (optionally) a release tag all agree.
- `tests/check_skills.py`: checks every skill has frontmatter with a matching `name` and a
  non-empty `description`.
- `make verify` and a GitHub Actions CI workflow that runs it on Python 3.11 and 3.13 for every push
  and pull request; every `uv run` uses `--locked`, so lockfile drift fails the build.
- `cli/semver_pep440.py`: the single SemVer -> PEP 440 converter, shared by the package build and
  `tests/check_versions.py`, so the release gate only accepts versions the package can build.
