---
description: Check that Kuanflow is installed and healthy in this repository (config, scripts, hooks, agents)
argument-hint: "[--agent <name>]"
---
Check the Kuanflow installation of this repository. Arguments: $ARGUMENTS

1. If the `kuanflow` CLI is on PATH, run `kuanflow doctor $ARGUMENTS`, show its output and exit code, and stop.
2. Otherwise, check by hand and report a table `Check | Result | Evidence` (PASS / WARN / FAIL). Do not fix
   anything; report only.
   - `.kuanflow/config.yaml` exists and parses as YAML; `.kuanflow/config.local.yaml` too, if present.
   - Required keys are present: `commands.build`, `commands.test`, `commands.verify`, `paths.work`.
   - The first word of each `commands.*` value resolves (a file in the repo or a program on PATH). Do not run
     the commands.
   - `.kuanflow/scripts/` holds `load-config.sh`, `guard-bash.sh` and `guard-protected-paths.sh`, and each is
     executable.
   - `python3` is available and can import PyYAML (`python3 -c "import yaml"`); without them the guards fail
     open.
   - The installed version (`kuanflow_version` in `.kuanflow/manifest.json`) is not older than
     `kuanflow.min_version`.
   - Agent hooks point to `.kuanflow/scripts/` (Claude Code: `hooks` in `.claude/settings.json`), for the agent
     named in `--agent`, or for every agent in the manifest.
   - Git hooks `.git/hooks/pre-commit` and `.git/hooks/pre-push` contain the Kuanflow block.
   - Managed blocks are intact: each `kuanflow:begin` has a matching `kuanflow:end` in `AGENTS.md` and
     `CLAUDE.md`.
3. End with one line: `Doctor: OK` or `Doctor: <n> problem(s)`.
