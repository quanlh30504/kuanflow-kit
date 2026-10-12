---
work: KF-000-analysis
phase: 0 (analysis, no code)
date: 2026-10-12
sources:
  PKG: docs/ai-workflow-packaging-guide.md   # referred to as docs/packaging.md in the brief (see Q-01)
  PB:  docs/ai-sdlc-workflow-playbook.md     # referred to as docs/playbook.md in the brief (see Q-01)
---
# Research — requirement inventory for Kuanflow

Facts only. Every row cites the section it comes from. Priority = proposed MVP cut (see `questions.md` §MVP);
`MVP` = must work end-to-end in v0.1, `later` = documented but deferred. Type: file / command / behavior / test.
Rows marked ⚠ have an open question in `questions.md`.

## 0. Environment facts (checked 2026-10-12 on the build machine)

| Tool | Installed | Notes |
|---|---|---|
| python3 | 3.12.3 | meets ≥ 3.11 (known decision) |
| uv / uvx | 0.11.21 | |
| PyYAML (system python3) | 6.0.1 | guard scripts need python3 + PyYAML (PKG §18.5) |
| Claude Code | 2.1.296 | `claude plugin validate` available → P7 can run it locally |
| Codex CLI | 0.162.1 | adapter formats to verify in P5 |
| OpenCode | 2.0.19 | adapter formats to verify in P5 |
| Kiro | `kiro-cli` 2.29.0 (no `kiro` binary) | adapter formats to verify in P5 |
| Orca | 1.4.224 | |
| node / npx | 22.21.1 / 10.9.4 | |
| gh | 2.45.0 | |
| bats | 1.10.0 (installed by human after Gate 0) | Q-24 resolved |
| ruff | missing globally | will come from `uv` dev deps (no action) |
| gitleaks, yq, markdownlint | missing | CI-only / optional (PKG §7, §12.1) |
| Copier | not installed | pinned in `cli/pyproject.toml` at P1; API verified in ADR-0001 |
| git remote | `github.com/quanlh30504/kuanflow-kit` | → GitHub Actions for CI |

Repo state: only `LICENSE` + the two docs; no tags.

## 1. Packaging requirements R1–R8 (PKG §1)

| ID | Requirement | Source | Type | Prio | How we will evidence it |
|---|---|---|---|---|---|
| R1 | Install into existing repo ≤ 10 min without breaking existing files | PKG §1, §16 | behavior/test | MVP | §12.5 fixture tests: pre-existing content outside blocks/keys byte-identical; E2E smoke (time is manual) |
| R2 | Upgrades never overwrite project customizations | PKG §1, §2, §10 | behavior/test | MVP | upgrade test with sample customizations (PKG §12.3.2) |
| R3 | Each project knows its Kuanflow version | PKG §1, §9.4 | file | MVP | `.kuanflow/manifest.json.kuanflow_version` + `.copier-answers.yml` |
| R4 | Skills written once, no hard-coded build commands | PKG §1, §7.2, §12.1 | test | MVP | `tests/check_skills.py` grep `mvnw|gradlew|npm run` |
| R5 | Changes tested before release | PKG §1, §12 | test | MVP | CI layers 1–3 blocking; evals gated |
| R6 | Rollback in minutes | PKG §1, §10.5 | behavior | MVP | `upgrade --to <old>` + `git revert`; test downgrade path |
| R7 | No data leak / unintended telemetry | PKG §1, §15 | behavior | MVP | no network in CLI except git fetch of `source`; tests use local `file://` git; secret scan in CI |
| R8 | Multiple agents (Claude main, Codex secondary), runs in Orca | PKG §1, §9.6 | test | MVP (claude, codex) / later (opencode, kiro) ⚠ Q-19 | per-adapter tests |

## 2. Monorepo layout (PKG §4)

| ID | Path | Notes | Prio |
|---|---|---|---|
| LAY-01 | `.claude-plugin/marketplace.json` | catalog, version synced | MVP (P7) |
| LAY-02 | `plugins/kuanflow/.claude-plugin/plugin.json` | ONLY manifest inside `.claude-plugin/` (PKG §4 hard rule) | MVP |
| LAY-03 | `plugins/kuanflow/skills/<10 skills>/` | see §9 below | MVP |
| LAY-04 | `plugins/kuanflow/agents/*.md` (9 files) | see §10 below | MVP |
| LAY-05 | `plugins/kuanflow/commands/*.md` (12 files) | w0…w10 + doctor | MVP |
| LAY-06 | `plugins/kuanflow/hooks/hooks.json` | plugin variant uses `${CLAUDE_PLUGIN_ROOT}` | MVP (P7) |
| LAY-07 | `plugins/kuanflow/scripts/{load-config,guard-bash,guard-protected-paths}.sh` | source of `.kuanflow/scripts/` | MVP |
| LAY-08 | `plugins/kuanflow/.mcp.json` | optional knowledge search | later |
| LAY-09 | `plugins/kuanflow/README.md` | | MVP |
| LAY-10 | `plugins/kuanflow-experimental/` | beta channel plugin | later |
| LAY-11 | `templates/project/{copier.yml, template/}` | `_subdirectory: template` | MVP ⚠ Q-09 |
| LAY-12 | `templates/knowledge-repo/` | | MVP (skeleton) / later (scripts) ⚠ Q-21 |
| LAY-13 | `cli/pyproject.toml`, `cli/src/kuanflow_cli/{main,detect,engine,manifest,doctor}.py` | | MVP |
| LAY-14 | `cli/src/kuanflow_cli/patchers/{managed_block,json_keys,toml_keys,gitignore}.py` | | MVP |
| LAY-15 | `cli/src/kuanflow_cli/adapters/{claude,codex,opencode,kiro,githooks}.py` (+ `base.py` PKG §18.2) | | MVP: claude, codex, githooks |
| LAY-16 | `cli/src/kuanflow_cli/migrations/` | per-version migrations | MVP (framework, no real migration) |
| LAY-17 | `evals/{fixtures,trigger,behavior}/` | | MVP (harness + min cases) |
| LAY-18 | `tests/` | scripts, hooks, template render | MVP |
| LAY-19 | `docs/{playbook.md, packaging.md, adr/}` | ⚠ Q-01 file names differ | MVP |
| LAY-20 | `CHANGELOG.md`, `CODEOWNERS`, `VERSION`, `.github/workflows/{ci,release}.yml` | | MVP |
| LAY-21 | `docs/rfc/NNNN-*.md` for MAJOR changes | PKG §14 | later (process) |

## 3. Generated project layout (PKG §6.1, §6.2) and ownership (PKG §6.4, §9.5)

| ID | Path in project | Owner class | Commit? | Prio |
|---|---|---|---|---|
| GEN-01 | `AGENTS.md` | managed-block (`kuanflow:begin/end`, PKG §6.5 text) | yes | MVP ⚠ Q-16 |
| GEN-02 | `CLAUDE.md` (block containing `@AGENTS.md`) | managed-block | yes | MVP |
| GEN-03 | `.kuanflow/config.yaml` | merge-required (Copier 3-way) | yes | MVP |
| GEN-04 | `.kuanflow/README.md` | template-managed | yes | MVP |
| GEN-05 | `.kuanflow/manifest.json` | CLI-managed (not hand-edited) | yes (not in personal) | MVP |
| GEN-06 | `.kuanflow/scripts/*` | template-managed | yes | MVP ⚠ Q-10 |
| GEN-07 | `.kuanflow/templates/.gitkeep` | local-owned | yes | MVP |
| GEN-08 | `.kuanflow/config.local.yaml`, `state.json`, `scratch/`, `cache/` | local / ignored | never | MVP (ignore lines) |
| GEN-09 | `kuan-workbench/work/.gitkeep`, `kuan-workbench/wiki/.gitkeep` | local-owned | yes | MVP |
| GEN-10 | `docs/adr/0000-template.md`, `docs/runbooks/README.md` | local-owned, only if absent | yes | MVP |
| GEN-11 | `.github/pull_request_template.md` (PKG §18.8 text) | managed-block | yes | MVP ⚠ Q-14 |
| GEN-12 | `.gitignore` (PKG §6.2 lines, varies by `artifacts.commit`) | managed-block | yes | MVP |
| GEN-13 | `orca.yaml`, `.worktreeinclude` (when `use_orca`) | PKG §6.4 says template-managed | yes | MVP ⚠ Q-13 |
| GEN-14 | `.copier-answers.yml` | Copier-managed, never hand-edited | yes | MVP |
| GEN-15 | `.github/workflows/kuanflow-update.yml` (PKG §10.4, "generated at init") | not classified in docs | yes | later ⚠ Q-13 |
| GEN-16 | `~/.kuanflow/{config.yaml, journal/, reports/}` | user-level, outside repo | n/a | MVP (skills write there; CLI does not create) |
| GEN-17 | `CLAUDE.local.md` | personal mode target; ignored line in block | never | MVP |

Ownership behavior matrix (PKG §9.5) — each cell becomes ≥ 1 test:

| ID | Class | init | upgrade | uninstall |
|---|---|---|---|---|
| OWN-01 | template-managed | create | hash unchanged → overwrite; modified → 3-way merge; conflict → markers + exit 3 | delete |
| OWN-02 | merge-required | create from answers + detection | 3-way merge (Copier) | delete |
| OWN-03 | managed-block | insert block, keep rest | replace only block content; block hand-edited → warn + backup + overwrite (PKG §10.3) | remove block |
| OWN-04 | managed-keys | merge by key, keep project keys | update only keys recorded in manifest; hand-edited key → warn, default update, keep with `--keep-local` (PKG §10.3) | remove exactly those keys |
| OWN-05 | local-owned | create only if absent | never touch | keep |
| OWN-06 | safety | never overwrite user-modified file without `--force`; every overwrite backed up to `.kuanflow/cache/backup/<timestamp>/`; `--dry-run` shows diff (PKG §9.5) | | |

## 4. Configuration (PKG §6.3, §7, §7.1)

| ID | Requirement | Source | Prio |
|---|---|---|---|
| CFG-01 | Config keys: `schema_version`, `kuanflow.min_version`, `project.{name,stack}`, `commands.{build,test,verify,single_test,lint}`, `paths.{work,wiki,scratch,adr,runbooks}`, `artifacts.commit`, `work.ticket_pattern`, `protected_paths[]`, `risk.fintech`, `workflows.enabled[]`, `debug.{services,budget{max_turns_total,classification,subagent,fix_rounds},allow_prod_log_access}`, `knowledge.repo`, `integrations.jira_project_key` | PKG §7.1 | MVP |
| CFG-02 | `guard.extra_block_patterns[]` (used by guard-bash, not in §7.1 sample) | PKG §18.4 | MVP ⚠ Q-11 |
| CFG-03 | JSON Schema v1 for config; rendered config validates | PKG §12.3, brief P3 | MVP |
| CFG-04 | Layering: defaults → org → project → local; later overrides earlier; printed by SessionStart | PKG §7 | MVP: project+local (§18.3) / later: defaults+org ⚠ Q-12 |
| CFG-05 | `paths.work`/`paths.wiki` renamable; `.kuanflow/` fixed | PKG §6.2 | MVP |
| CFG-06 | Copier questions: project_name, stack (java-maven/java-gradle/node/python/other), build/test/verify/single_test cmds (stack defaults), fintech, protected_paths, services, artifacts_commit, use_orca, knowledge_repo, jira_project_key, kuanflow_version | PKG §6.3 | MVP ⚠ Q-11 |
| CFG-07 | `_min_copier_version: "9.0.0"`, `_skip_if_exists` list, `_answers_file`, `_templates_suffix: .jinja` | PKG §6.3 | MVP (verify syntax) |
| CFG-08 | Config contains only env var *names*, never secret values | PKG §15 | MVP (schema + check) |
| CFG-09 | Config schema N must be readable by N+1 with warning | PKG §13.3 | later (no N+1 yet) |

## 5. CLI commands, flags, exit codes (PKG §9.2, §9.7, §9.8, §10, §18.2)

| ID | Command / flag | Behavior | Prio |
|---|---|---|---|
| CMD-01 | `init --here` | find root, detect, render, patch, adapters, manifest, doctor | MVP |
| CMD-02 | `init --agent a,b` | default = detected agents | MVP |
| CMD-03 | `init --personal` | see §8 | MVP |
| CMD-04 | `init --template project\|knowledge-repo` | default project | MVP |
| CMD-05 | `init --yes` | accept all detected/defaults, no prompts | MVP |
| CMD-06 | `init --dry-run` | no file change; show diff | MVP |
| CMD-07 | `init --root <path>` | monorepo sub-service (PKG §9.7) | MVP |
| CMD-08 | `init --data-file <yml>` | answers file for bulk install (PKG §9.10, §18.2) — not in §9.2 table | MVP (needed by tests) ⚠ Q-15 |
| CMD-09 | `init --promote-to-project` | switch personal → project (PKG §9.8) — not in §9.2 table | later ⚠ Q-15 |
| CMD-10 | `upgrade [--to vX.Y.Z]` | default latest; migrations → Copier update → blocks/keys → adapters → manifest → doctor | MVP |
| CMD-11 | `upgrade --check` | exit 2 if newer exists, 0 otherwise | MVP |
| CMD-12 | `upgrade --dry-run` | diff only | MVP |
| CMD-13 | `upgrade --yes` | used by CI bot (PKG §10.4) | MVP |
| CMD-14 | `upgrade --force` | overwrite user-modified files (PKG §9.5, §18.2) | MVP |
| CMD-15 | `upgrade --keep-local` | keep project value of hand-edited managed keys (PKG §10.3) | MVP |
| CMD-16 | `self upgrade` | update CLI itself | MVP (thin wrapper over uv) ⚠ Q-15 |
| CMD-17 | `agent add <a>` / `agent remove <a>` | add→remove returns repo to prior hash state | MVP |
| CMD-18 | `status` | version, agents, files modified vs original, hand-edited managed blocks | MVP |
| CMD-19 | `doctor [--agent <a>]` | config valid, verify cmd, guards loaded per agent, Tier-2 notice, python3/PyYAML present | MVP ⚠ Q-17 |
| CMD-20 | `promote <draft>` | drafts → `docs/adr` (numbered, `status: accepted`) / `docs/runbooks`; delete draft | MVP ⚠ Q-18 |
| CMD-21 | `uninstall [--dry-run]` | remove per manifest; keep `docs/`, `kuan-workbench/` | MVP |
| CMD-22 | Exit codes | 0 ok · 1 error · 2 update available (`--check`) · 3 conflicts | MVP |
| CMD-23 | Root resolution | walk up to first `.kuanflow/`, else git toplevel; `--root` overrides | MVP |
| CMD-24 | Clean worktree required for init (except personal) and upgrade | PKG §9.7, §10.2, §18.2 | MVP |
| CMD-25 | Summary + doctor result printed after init; no Copier `_message_after_copy` | PKG §6.3, §9.7 | MVP |
| CMD-26 | Warn if agent config violates org model/provider policy | PKG §15 | later ⚠ Q-17 |
| CMD-27 | Distribution: `uvx --from git+…@vX.Y.Z kuanflow init …`; `uv tool install kuanflow-cli --from git+…` | PKG §9.2 | MVP ⚠ Q-06 |
| CMD-28 | Single-file executable per OS | PKG §9.9 | later |

## 6. Detector (PKG §9.7)

| ID | Signal → conclusion | Prio |
|---|---|---|
| DET-01 | `mvnw`/`pom.xml` → java-maven, `./mvnw -q …` | MVP ⚠ Q-20 (no wrapper) |
| DET-02 | `gradlew`/`build.gradle(.kts)` → java-gradle, `./gradlew …` | MVP |
| DET-03 | `package.json` → node; read `scripts.test`, `scripts.build` | MVP ⚠ Q-20 |
| DET-04 | `src/main/resources/db/migration` → suggest in `protected_paths` | MVP |
| DET-05 | `.claude/`, `.codex/`, `.opencode/`, `.kiro/` or CLI on PATH → suggest `--agent` list | MVP |
| DET-06 | `orca.yaml` or Orca on machine → `use_orca` | MVP |
| DET-07 | Every detected value shown for confirmation; `--yes` accepts | MVP |

## 7. Manifest (PKG §9.4)

| ID | Field | Prio |
|---|---|---|
| MAN-01 | `kuanflow_version` | MVP |
| MAN-02 | `installed_at` (ISO-8601 with offset) — must not change on idempotent re-init ⚠ Q-22 | MVP |
| MAN-03 | `mode`: project \| personal | MVP |
| MAN-04 | `agents[]` | MVP |
| MAN-05 | `source` (git URL @ tag) — also used to fetch old version for 3-way merge | MVP |
| MAN-06 | `files[]`: `path`, `owner`, `sha256`; `block` for managed-block; `keys[]` for managed-keys; `agent` for adapter files | MVP |
| MAN-07 | Manifest schema version (compat matrix "Manifest version 1", PKG §13.3) — no field shown in sample | MVP ⚠ Q-22 |

## 8. Personal vs project mode (PKG §9.8)

| ID | Aspect | project | personal | Prio |
|---|---|---|---|---|
| PER-01 | Kuanflow files | committed via PR | listed in `.git/info/exclude` | MVP |
| PER-02 | AGENTS.md block | yes | no — `CLAUDE.local.md` / agent-local file | MVP ⚠ Q-16 |
| PER-03 | `artifacts.commit` | minimal | none | MVP |
| PER-04 | git hooks | via repo hook manager | local `.git/hooks` | MVP ⚠ Q-08 |
| PER-05 | `git status` clean after init | — | must hold (test) | MVP ⚠ Q-16 |
| PER-06 | Dirty tree allowed | no | yes (`allow_dirty=personal`, PKG §18.2) | MVP |

## 9. Adapters (PKG §9.6, §18.1, §18.2)

| ID | Agent | Skills | Subagents | Hook guard | Entry | Tier | Prio |
|---|---|---|---|---|---|---|---|
| ADP-01 | claude | `.claude/skills/` | `.claude/agents/*.md` | `.claude/settings.json` managed keys `hooks`, `permissions.deny` → `.kuanflow/scripts/*` | skills as slash commands | 1 | MVP ⚠ Q-16 |
| ADP-02 | codex | `.agents/skills/` | `.codex/agents/*.toml` generated from source | `.codex/hooks.json` (needs hook enable + trust) | skills | 1 | MVP (verify formats) |
| ADP-03 | opencode | reads `.agents/skills/`, `.claude/skills/` | `.opencode/agents/*.md` | thin JS plugin calling scripts | skills / `.opencode/commands` | 2 | ⚠ Q-19 |
| ADP-04 | kiro | install skills + declare in `.kiro/agents/*.json` resources | — | — (outside-agent guard only) | skills | 2 | ⚠ Q-19 |
| ADP-05 | githooks | — | — | pre-commit/pre-push calling same scripts; always installed by init | — | n/a | MVP ⚠ Q-08 |
| ADP-06 | Rules | one physical skill copy per location an agent reads; scripts in repo, no `${CLAUDE_PLUGIN_ROOT}`; adapters write thin wrappers; each adapter declares `name`, `tier`, `tested_versions`, `detect/plan_install/plan_upgrade/plan_remove/doctor` | | | | | MVP |
| ADP-07 | Incompatible agent version → skip adapter, report in doctor | PKG §10.3 | | | | | MVP |
| ADP-08 | `settings.json` permissions.deny: `Read(./.env)`, `Read(./.env.*)`, `Read(./**/secrets/**)` | PKG §18.1 | | | | | MVP (verify syntax) |

## 10. Upgrade, conflicts, rollback, migrations (PKG §10)

| ID | Requirement | Prio |
|---|---|---|
| UPG-01 | Flow: clean tree → read manifest + fetch target → migrations → Copier 3-way → blocks/keys → adapters → conflicts? exit 3 : 0 → manifest + doctor | MVP |
| UPG-02 | Migrations between old and new version run in order; idempotent; tested | MVP (framework + test migration) |
| UPG-03 | Conflict table (PKG §10.3): template-managed → markers `<<<<<<<`; managed block edited → warn/backup/overwrite; managed key edited → warn, `--keep-local`; incompatible adapter → skip + doctor | MVP |
| UPG-04 | Rollback: `upgrade --to <old>` works (downgrade) | MVP |
| UPG-05 | Uninstall: remove files per manifest, blocks and keys; keep `docs/`, `kuan-workbench/` | MVP |
| UPG-06 | Project CI bot `kuanflow-update.yml`: weekly, opens PR only for PATCH/MINOR, never merges | later |
| UPG-07 | Adapter-installed template-managed files (skills etc.) also need 3-way merge — Copier does not manage them ⚠ Q-09 | MVP |

## 11. Hooks & guard scripts (PKG §5.5, §18.3–18.5)

| ID | Rule | Prio |
|---|---|---|
| SCR-01 | Hooks read JSON on stdin; exit 2 blocks; reason on stderr | MVP |
| SCR-02 | load-config: find root; print version (manifest → plugin.json → unknown); print config + local; warn if version < `kuanflow.min_version`; never fails session; silent if no config | MVP |
| SCR-03 | guard-bash blocks: force push to main/master/release; direct push to main/master; kubectl/helm prod context/namespace; psql/mysql/mongosh/redis-cli prod; `rm -rf /|~|$HOME|.|..`; `drop database|schema|table`; reading `.env` via cat/less/head/tail/cp/scp; project `guard.extra_block_patterns` from config + local | MVP |
| SCR-04 | guard-bash allows normal commands (e.g. `./mvnw -q test`) | MVP |
| SCR-05 | guard-protected-paths: block edit of EXISTING file matching `protected_paths` (config + local); new files allowed; missing python3/PyYAML → allow + doctor warns; test paths with special characters | MVP |
| SCR-06 | Scripts executable (`chmod +x`); doctor checks | MVP |
| SCR-07 | Plugin hooks.json uses `${CLAUDE_PLUGIN_ROOT}/scripts/…`; CLI-installed hooks point to `.kuanflow/scripts/` | MVP |

## 12. Skills (PB §8.2, §8.4–8.6; PKG §4, §7.2, §11.3)

All skills: frontmatter `name` = dir, `description` says when (and when not) to use; first step reads effective config; stop if required key missing; no hard-coded commands/paths; domain blocks gated by `risk.fintech`; long content in side files; no secrets/real data.

| ID | Skill | Files (PKG §4 / PB §8.3) | Content source | Output | Prio |
|---|---|---|---|---|---|
| SKL-01 | daily-plan | SKILL.md | PB W0, §13.1 | `~/.kuanflow/journal/YYYY/MM/YYYY-MM-DD.md` | MVP |
| SKL-02 | clarify-requirements | SKILL.md, `checklists/fintech-questions.md` | PB W1 | `questions.md` | MVP |
| SKL-03 | write-spec | SKILL.md, `templates/spec.md` | PB W2, §13.2 | `spec.md` | MVP |
| SKL-04 | research-solution | SKILL.md | PB W3, §4 | `research.md`, `options.md` | MVP |
| SKL-05 | verify-agent-output | SKILL.md (full text PB §8.4) | PB W8, §8.4, §13.4 | `review.md` | MVP |
| SKL-06 | fintech-review | SKILL.md (full text PB §8.5) | PB §8.5 | section in `review.md` | MVP |
| SKL-07 | debug-incident | SKILL.md (PB §8.6), `scripts/collect_context.sh`, `schemas/context.schema.json` | PB §6, §8.6 | `incident-notes.md` | MVP ⚠ Q-07 |
| SKL-08 | write-postmortem | SKILL.md, `templates/postmortem.md` | PB §13.5, §7 | `drafts/postmortem.md` | MVP |
| SKL-09 | work-report | SKILL.md | PB W9 | `~/.kuanflow/reports/…` | MVP |
| SKL-10 | knowledge-gardening | SKILL.md | PB §7.4, §9.2 | stale wiki list + PR proposals | MVP |
| SKL-11 | W4 plan / W5 implement / W6 test / W10 skill-update rely on external Superpowers skills (`writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `writing-skills`) | PB §5 table, §8.1 | — | — | ⚠ Q-04 |

## 13. Subagents (PKG §4; PB §6.4, §8.7)

| ID | Agent | Content in docs | Tools | Prio |
|---|---|---|---|---|
| AGT-01 | codebase-locator | description only (PB W3) | read-only | MVP |
| AGT-02 | codebase-analyzer | full text PB §8.7 | Read, Grep, Glob | MVP |
| AGT-03 | pattern-finder | description only (PB W3) | read-only | MVP |
| AGT-04 | test-writer | full text PB §8.7 | Read, Grep, Glob, Write, Bash | MVP |
| AGT-05 | adversarial-reviewer | full text PB §8.7 | Read, Grep, Glob, Bash (no Write) | MVP |
| AGT-06..09 | rca-timeline, rca-change-correlation, rca-code-path, rca-past-incident | scope table PB §6.4 | read-only | MVP |
| AGT-10 | rca-data-state, consolidator | PB §6.2/§6.4 mention; not in PKG §4 | — | later ⚠ Q-05 |
| AGT-11 | Tools allowlist enforced by static check; reviewer has no Write | PKG §12.1 — allowlist not defined | | MVP ⚠ Q-05 |

## 14. Slash commands (PKG §4, §5.4)

| ID | Command | Calls | Prio |
|---|---|---|---|
| CMS-01..11 | `w0-daily, w1-clarify, w2-spec, w3-research, w4-plan, w5-implement, w6-test, w7-debug, w8-verify, w9-report, w10-capture` | pattern: read config → call skill → write artifact in right place (PKG §5.4 full text for w8) | MVP ⚠ Q-04 |
| CMS-12 | `doctor` | not described ⚠ Q-17 | MVP |
| CMS-13 | Frontmatter `description`, `argument-hint`; `$ARGUMENTS` | PKG §5.4 | MVP |
| CMS-14 | Invocation name `/kuanflow:<cmd>` | PKG intro, §6.5 | ⚠ Q-16 |

## 15. Templates

| ID | Item | Source | Prio |
|---|---|---|---|
| TPL-01 | Project template renders §6.1 tree for java-maven, java-gradle, node (+python, other) | PKG §6, §12.3 | MVP |
| TPL-02 | Answer fixtures `tests/answers/<stack>.yml` | PKG §12.3 | MVP |
| TPL-03 | PR template text | PKG §18.8 | MVP |
| TPL-04 | orca.yaml + .worktreeinclude text | PKG §18.9 | MVP |
| TPL-05 | ADR template (PB §13.6), runbooks README | PKG §6.1 | MVP |
| TPL-06 | Knowledge repo: `postmortems/`, `runbooks-shared/`, `taxonomy.md` (PB §7.5), postmortem + ADR templates, `scripts/build-index.py`, `scripts/stale-wiki-check.sh`, CI frontmatter check (`id`, `services`, `category ∈ taxonomy`, `signatures`, `status`) | PKG §6.6, PB §7 | MVP skeleton+frontmatter check / later index ⚠ Q-21 |
| TPL-07 | Copier `_migrations` example (v2 rename) | PKG §6.3 | ⚠ Q-09 |

## 16. Testing layers (PKG §12) and CLI tests (PKG §12.5)

| ID | Layer / test | Expectation | Prio |
|---|---|---|---|
| TST-01 | L1 static: SKILL frontmatter, agent frontmatter + tool allowlist, plugin validate, version sync, no hard-coded build cmds, secret scan, banned prompt patterns (PKG §15) | blocking | MVP |
| TST-02 | L1 markdownlint, mermaid | | later ⚠ Q-25 |
| TST-03 | L2 bats for every guard rule (block + allow cases, special chars) | blocking | MVP |
| TST-04 | L3 render all stacks; config validates against schema | blocking | MVP |
| TST-05 | L3 update from old version with sample customizations | blocking | MVP |
| TST-06 | L4 trigger eval ("check my diff before PR" → verify-agent-output) | gated by key | MVP harness / LLM run gated |
| TST-07 | L5 behavior evals — 7 cases PKG §12.4 table; `runs`, `pass_threshold`, deterministic assertions | gated by key | MVP (≥ 1 case wired) / later (all 7) |
| TST-08 | CLI fixtures: empty, Maven+CLAUDE.md+.gitignore, Gradle+settings.json, monorepo, Spec Kit repo | | MVP |
| TST-09 | `init --yes` on each fixture: doctor green, pre-existing content intact outside blocks/keys | | MVP |
| TST-10 | `init --dry-run`: no change; correct diff | | MVP |
| TST-11 | `init` twice: second run no change | | MVP |
| TST-12 | `upgrade` from previous with customizations: kept; local-owned untouched; conflict → 3 | | MVP |
| TST-13 | `upgrade --check`: 2 / 0 | | MVP |
| TST-14 | `agent add codex` → `remove`: hash-identical to before | | MVP |
| TST-15 | `uninstall`: all removed per manifest; docs/ + kuan-workbench/ intact | | MVP |
| TST-16 | `--personal`: `git status` clean | | MVP |

## 17. Versioning, release, governance, security (PKG §11, §13–15)

| ID | Requirement | Prio |
|---|---|---|
| REL-01 | One version for plugin.json, marketplace.json, VERSION, CLI; `check_versions.py [--tag]` | MVP ⚠ Q-03 |
| REL-02 | release.yml: tag `v*` → version check → eval gate (stable only) → changelog section → `gh release` (`--prerelease` for beta) | MVP |
| REL-03 | CHANGELOG by behavior (Added/Changed/Deprecated/Migration) | MVP |
| REL-04 | Beta channel / `kuanflow-experimental` / pinned marketplace refs | later |
| REL-05 | Compatibility matrix in README | MVP |
| REL-06 | CODEOWNERS (PKG §14 text, `<org>` placeholders) | MVP |
| REL-07 | Deprecation policy (`[DEPRECATED — use X]`) | later (process) |
| SEC-01 | No runtime download of scripts; hooks reviewed; secret scan; fake data in fixtures | MVP |
| SEC-02 | Org URLs placeholders `<org>`, configurable | MVP |

## 18. Doc defects found (do not fix docs; recorded for questions.md)

1. File names: brief says `docs/packaging.md` / `docs/playbook.md`; repo has `ai-workflow-packaging-guide.md` / `ai-sdlc-workflow-playbook.md` (PKG §4 says `docs/playbook.md = ai-sdlc-workflow-playbook.md`).
2. `requires-python = ">=3.10"` (PKG §18.2) vs known decision ≥ 3.11.
3. `uvx --from git+…/kuanflow.git@vX kuanflow` (PKG §9.2) cannot work if `pyproject.toml` lives in `cli/` without `#subdirectory=cli`, and a wheel built from `cli/` does not contain `plugins/` or `templates/`.
4. Copier `_migrations` path `templates/project/migrations/…` (PKG §6.3) vs `cli/src/kuanflow_cli/migrations/` (PKG §4).
5. Config layers: `plugin/defaults/config.yaml` + `~/.config/kuanflow/org.yaml` (PKG §7) vs user config `~/.kuanflow/config.yaml` (PKG §6.2) vs load-config.sh reading only project + local (PKG §18.3).
6. `/kuanflow:<cmd>` naming works for the plugin channel; CLI-installed `.claude/commands` are not namespaced the same way (to verify).
7. copier.yml defaults for `node` fall into the `else` branch (`make build`), while the detector says to read `package.json` scripts.
8. CI: `bats tests/` (PKG §18.6) vs `bats tests/bats` (brief); `evals/run.sh` (PKG §12.4) vs `evals/run_all.sh --threshold-file evals/thresholds.yaml` (PKG §18.6).
9. load-config.sh warning text is Vietnamese; repo language rule says English.
10. `orca.yaml` listed as template-managed but it is a root file the project may already own (detector uses its presence as a signal).
