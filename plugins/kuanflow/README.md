# Kuanflow plugin content

This directory is the single source of Kuanflow's agent content: skills, subagents, slash commands and the
guard scripts the hooks call. The `kuanflow` CLI copies it into each project for every agent it supports
(main channel). The same directory is also a Claude Code plugin (optional channel).

Content is project-independent: skills and commands never hard-code build commands or project paths. They
read config keys from `.kuanflow/config.yaml` (committed) and `.kuanflow/config.local.yaml` (personal,
ignored; it overrides the project file). A missing required key means: stop and ask, never guess.

## Skills

| Skill | Use when | Output |
|---|---|---|
| `daily-plan` | Start of the day (W0) | `~/.kuanflow/journal/YYYY/MM/YYYY-MM-DD.md` |
| `clarify-requirements` | New ticket or requirement, before any design (W1) | `questions.md` |
| `write-spec` | Questions answered (W2) | `spec.md` |
| `research-solution` | Understand current code, compare options (W3) | `research.md`, `options.md`, ADR draft |
| `verify-agent-output` | Before claiming done, committing or opening a PR (W8) | `review.md` |
| `fintech-review` | Diff touches money, orders, accounts, settlement | `## Fintech review` in `review.md` |
| `debug-incident` | Production alert, incident, unknown cause (W7) | `incident-notes.md` |
| `write-postmortem` | After an incident is fixed or mitigated (W10) | `drafts/postmortem.md` |
| `work-report` | End of day or week (W9) | `~/.kuanflow/reports/…` |
| `knowledge-gardening` | Weekly wiki freshness check | stale page list + PR |

Work-folder artifacts live in `<paths.work>/<TICKET>-<slug>/`. The current work item is resolved in this
order: env `KUANFLOW_WORK` → ticket key in the branch name (`work.ticket_pattern`) → `.kuanflow/state.json`
(`{"work": "<folder>"}`) → ask. Temporary or sensitive data goes to `<paths.scratch>/<work-id>/` only.

Side files: `clarify-requirements/checklists/fintech-questions.md`, `write-spec/templates/spec.md`,
`write-postmortem/templates/postmortem.md`, `debug-incident/schemas/context.schema.json` and
`debug-incident/scripts/collect_context.sh` (builds a masked `context.json` ≤ 50 KB from local files; no
network). A project can override a template by putting a file with the same name in `.kuanflow/templates/`.

## Subagents

All are read-only (no `Write`/`Edit`) except `test-writer`. Tool allowlist: `Read`, `Grep`, `Glob`, `Bash`,
`Write`, `Edit`, `WebFetch`, `WebSearch`.

| Agent | Role | Tools |
|---|---|---|
| `codebase-locator` | Where the code for a question lives | Read, Grep, Glob |
| `codebase-analyzer` | How the code works today (no suggestions) | Read, Grep, Glob |
| `pattern-finder` | Patterns in use, which are deprecated | Read, Grep, Glob |
| `test-writer` | Tests from acceptance criteria, without reading the implementation | Read, Grep, Glob, Write, Bash |
| `adversarial-reviewer` | Hunts defects in a diff (W8) | Read, Grep, Glob, Bash |
| `rca-timeline` | What happened, in order | Read, Grep, Glob |
| `rca-change-correlation` | Which change inside the window | Read, Grep, Glob, Bash |
| `rca-code-path` | Which code path fails, under which conditions | Read, Grep, Glob |
| `rca-past-incident` | Seen before? How was it handled? | Read, Grep, Glob |

## Commands

| Command | Does |
|---|---|
| `w0-daily` | daily-plan |
| `w1-clarify` | clarify-requirements |
| `w2-spec` | write-spec |
| `w3-research` | research-solution (+ locator, analyzer, pattern-finder) |
| `w4-plan` | plan.md (self-contained; uses Superpowers `writing-plans` if installed) |
| `w5-implement` | one plan phase with verify evidence (self-contained; Superpowers `executing-plans` / `test-driven-development` if installed) |
| `w6-test` | tests from ACs via test-writer (self-contained) |
| `w7-debug` | debug-incident, or the basic bug steps |
| `w8-verify` | verify-agent-output (+ fintech-review) |
| `w9-report` | work-report |
| `w10-capture` | knowledge capture: postmortem, wiki, ADR/runbook drafts, skill updates (self-contained) |
| `doctor` | runs `kuanflow doctor`, or the same checks by hand |

Each `wN` command stops when `wN` is not listed in `workflows.enabled`. With the plugin channel the commands
are namespaced (`/kuanflow:w8-verify`); how the CLI-installed copies are invoked depends on the agent.

## Guard scripts

`scripts/` holds the hook scripts. The CLI installs them into `.kuanflow/scripts/`; the plugin channel runs
them from the plugin directory. Hooks read JSON on stdin; exit `2` blocks with the reason on stderr.

| Script | Hook | Behaviour |
|---|---|---|
| `load-config.sh` | SessionStart | Prints the installed version and the effective config; warns when older than `kuanflow.min_version`; never fails |
| `guard-bash.sh` | PreToolUse (Bash) | Blocks force/direct pushes to main, production clusters and datastores, destructive `rm`/SQL, reading `.env`, and `guard.extra_block_patterns` |
| `guard-protected-paths.sh` | PreToolUse (Edit/Write) | Blocks edits of existing files matching `protected_paths`; new files are allowed |

The guards need `python3` (and PyYAML for project config). Without them they fail open, and
`kuanflow doctor` reports it. A regex guard is a safety net, not a security boundary.

## Config-key contract

Keys the content reads. Paths are relative to the project root.

| Key | Used by | Meaning |
|---|---|---|
| `schema_version` | CLI | Config schema version |
| `kuanflow.min_version` | `load-config.sh`, `doctor` | Oldest Kuanflow version the project accepts |
| `project.name`, `project.stack` | CLI | Service name and stack |
| `commands.build` | verify-agent-output, doctor | Build command |
| `commands.test` | verify-agent-output, test-writer, w6, doctor | Unit test command |
| `commands.verify` | verify-agent-output, debug-incident, w4, w5, w7, doctor | Command that must pass before "done" |
| `commands.single_test` | test-writer, debug-incident, w4, w5, w6 | Run one test; `{test}` is the placeholder |
| `commands.lint` | verify-agent-output | Linter |
| `commands.*` | w4, w5, w7, w8, doctor | All of the above |
| `paths.work` | all work-folder skills and commands | Work folders `<TICKET>-<slug>/` |
| `paths.wiki` | research-solution, clarify-requirements, knowledge-gardening, w3, w10 | Generated wiki |
| `paths.scratch` | debug-incident, collector, w7 | Temporary/sensitive data (inside `.kuanflow/`, ignored) |
| `paths.adr` | research-solution, knowledge-gardening, w3 | Approved ADRs (promote target; never written by agents) |
| `paths.runbooks` | research-solution, knowledge-gardening | Approved runbooks (promote target) |
| `artifacts.commit` | CLI | Which artifacts are committed |
| `work.ticket_pattern` | work-folder skills, w1 | Regex for the ticket key in the branch name |
| `protected_paths` | guard-protected-paths.sh, verify-agent-output, test-writer, w5 | Globs agents must not modify |
| `risk.fintech` | clarify-requirements, write-spec, verify-agent-output, fintech-review, w1, w2, w8 | Turns on fintech checks |
| `workflows.enabled` | every `wN` command | Workflows this project uses |
| `debug.services` | debug-incident, collector, w7 | Services in scope for incidents |
| `debug.budget` | debug-incident, collector, w7 | `max_turns_total`, `classification`, `subagent`, `fix_rounds` |
| `debug.allow_prod_log_access` | debug-incident, w7 | When false, agents never query production logs |
| `knowledge.repo` | clarify-requirements, research-solution, debug-incident, write-postmortem, knowledge-gardening, w3, w10 | Knowledge repo (postmortems, shared runbooks) |
| `integrations.jira_project_key` | daily-plan, work-report, w0, w9 | Ticket filter |
| `guard.extra_block_patterns` | guard-bash.sh | Extra regexes to block |

## Static checks

`python3 tests/check_skills.py plugins/kuanflow` (part of `make verify`) enforces: skill and agent
frontmatter, the tool allowlist and read-only roles, command frontmatter, no hard-coded build commands
(except inside a fenced block right after `<!-- kuanflow:example -->`), and no banned patterns
(prompt-injection phrases, disabled TLS, downloads from real hosts).
