---
work: KF-004-p3-templates
phase: P3 — Templates
parent_plan: kuan-workbench/work/KF-001-plan/plan.md
status: in progress
---
# P3 — Templates

Sources: PKG = `docs/packaging.md` (§6.1–6.6, §7.1, §18.8, §18.9), PB = `docs/playbook.md` (§7.3–7.5, §13.5–13.7),
ADR-0002 (Copier engine). Gate 0 answers Q-09, Q-10, Q-11, Q-13, Q-16, Q-21 apply. All content and messages are
English. All commands run as `uv run --locked …` from the repo root (C7r).

Execution: sub-agents (user asked for agent orchestration). Agents work in the main tree on **disjoint files**
and do not commit; the coordinator commits after each step. Order: T3.1 (tests, RED) → {T3.2 ∥ T3.3+T3.4 ∥ T3.5}
→ GREEN → adversarial review → fix rounds → DoD.

## Contracts (tests are written against THESE, not against code)

### Engine (T3.2) — `cli/src/kuanflow_cli/engine.py`

C23. **`content_root() -> Path`** — the directory that holds `VERSION`, `templates/` and `plugins/kuanflow/`.
     Installed wheel: `kuanflow_cli/_content/`; source tree / editable install: the repo root. Raises
     `FileNotFoundError` when neither holds `templates/project/copier.yml`. **`current_version() -> str`** =
     stripped `<content_root>/VERSION` (SemVer). The wheel ships `VERSION` at `kuanflow_cli/_content/VERSION`
     (C11 amended).

C24. **`assemble_template(dest, versions, *, template="project") -> Path`**
     - `versions`: non-empty sequence of `(semver, source_root)`; `source_root` has the C23 layout. Versions must
       be strictly ascending (SemVer order, prerelease < release) and parse with `kuanflow_cli.semver.parse`,
       else `ValueError` (nothing written).
     - `dest` is removed first if it exists, then `git init`. For each version, oldest first: the working tree
       (everything but `.git`) is emptied, `<source_root>/templates/<template>/**` is copied in; for
       `template="project"` every file of `<source_root>/plugins/kuanflow/scripts/` is copied to
       `template/.kuanflow/scripts/` **with mode 0755** whatever the source mode (D-P2-6, SCR-06). Then
       `git add -A`, one commit, lightweight tag `v<semver>`.
     - Reproducible: fixed author/committer name `kuanflow`, e-mail `kuanflow@localhost`, date
       `2000-01-01T00:00:00+00:00`, message `kuanflow v<semver>`; git runs with `GIT_CONFIG_GLOBAL=/dev/null`,
       `GIT_CONFIG_NOSYSTEM=1` (user hooks, signing, templates do not apply). Same inputs → same HEAD SHA.
     - HEAD is exactly on the last tag (`git describe --tags` = `v<last>`). Returns `dest`.
     - Unknown `template` (no `templates/<template>/copier.yml` in a source) → `ValueError`.

C25. **`render(dst, data, *, version=None, content=None, template="project") -> None`**
     - `version` defaults to `current_version()`, `content` to `content_root()`.
     - Creates `dst` if missing; assembles `<dst>/.kuanflow/cache/template-repo` with `[(version, content)]`;
       calls `copier.run_copy(".kuanflow/cache/template-repo", ".", data=…, defaults=True, vcs_ref="v<version>",
       quiet=True, unsafe=False)` **with cwd = dst** (restored afterwards, also on error).
     - `data` is copied; `kuanflow_version` is set to `version` when the caller did not give it (Q-11).
     - Result: `<dst>/.copier-answers.yml` has `_src_path: .kuanflow/cache/template-repo` and
       `_commit: v<version>`, plus every answer. Copier errors propagate (P4 maps them).

### Project template (T3.3, T3.4) — `templates/project/`

C26. **`copier.yml`** — `_min_copier_version: "9.18.2"`, `_subdirectory: template`,
     `_answers_file: .copier-answers.yml`, `_templates_suffix: .jinja`. No `_tasks`, `_migrations`,
     `_jinja_extensions`, `_message_after_copy`, no `_copier_conf.src_path`. `_skip_if_exists` = exactly
     `docs/adr/*.md`, `docs/runbooks/*.md`, `kuan-workbench/**`, `.kuanflow/templates/**`,
     `.kuanflow/config.local.yaml`, `orca.yaml` (Q-13; `.claude/skills/**` removed — adapters, not Copier).
     Questions (PKG §6.3 + Q-11): `project_name` (str), `stack` (choices `java-maven, java-gradle, node, python,
     other`, default `java-maven`), `build_cmd`, `test_cmd`, `verify_cmd`, `single_test_cmd`, `lint_cmd`,
     `ticket_pattern` (default `[A-Z][A-Z0-9]+-[0-9]+`), `fintech` (bool, true), `protected_paths` (yaml, default
     `["src/main/resources/db/migration/**", "**/legacy/**"]`), `services` (yaml, `[]`), `artifacts_commit`
     (choices `minimal, full, none`, default `minimal`), `use_orca` (bool, true), `knowledge_repo` (str, `""`),
     `jira_project_key` (str, `""`), `kuanflow_version` (str, default `""` — the CLI fills it, C25).
     Stack defaults (PKG §6.3; `lint` added, D-P3-1):

     | stack | build | test | verify | single_test | lint |
     |---|---|---|---|---|---|
     | java-maven | `./mvnw -q -DskipTests package` | `./mvnw -q test` | `./mvnw -q verify` | `./mvnw -q -Dtest={test} test` | `./mvnw -q spotless:check` |
     | java-gradle | `./gradlew assemble` | `./gradlew test` | `./gradlew check` | `./gradlew test --tests {test}` | `./gradlew spotlessCheck` |
     | node, python, other | `make build` | `make test` | `make verify` | `make test TEST={test}` | `make lint` |

C27. **Rendered tree** (`render(dst, answers)`), files under `templates/project/template/`:
     - `.copier-answers.yml` (from `{{ _copier_conf.answers_file }}.jinja`, `{{ _copier_answers|to_nice_yaml }}`).
     - `.kuanflow/config.yaml` (C28), `.kuanflow/README.md`, `.kuanflow/templates/.gitkeep`,
       `.kuanflow/scripts/{load-config,guard-bash,guard-protected-paths}.sh` — byte-identical to
       `plugins/kuanflow/scripts/*` and executable (Q-10; not kept in `templates/`).
     - `kuan-workbench/work/.gitkeep`, `kuan-workbench/wiki/.gitkeep`, `docs/adr/0000-template.md`,
       `docs/runbooks/README.md`.
     - `orca.yaml` only when `use_orca` is true (PKG §18.9 content, English comment); no empty file otherwise.
     - Nothing else outside `.kuanflow/cache/`: no `AGENTS.md`, `CLAUDE.md`, `.gitignore`,
       `.worktreeinclude`, `.github/` (those are patcher blocks, C30), no `.jinja` file names, no `copier.yml`.
     - `.kuanflow/README.md` names `config.yaml`, `config.local.yaml`, `scripts/`, `templates/`,
       `manifest.json`, `kuanflow upgrade`, `kuanflow doctor`, and says not to edit `.copier-answers.yml`.
     - `docs/adr/0000-template.md` = PB §13.6 structure in English (frontmatter `id`, `title`, `status`, `date`,
       `deciders`; five `##` sections).

C28. **`.kuanflow/config.yaml`** parses with `yaml.safe_load` to exactly the PKG §7.1 key set plus
     `guard.extra_block_patterns` (Q-11):
     `schema_version: 1`; `kuanflow.min_version` = `kuanflow_version`; `project.{name,stack}`;
     `commands.{build,test,verify,single_test,lint}` = the `*_cmd` answers; `paths` = `work: kuan-workbench/work`,
     `wiki: kuan-workbench/wiki`, `scratch: .kuanflow/scratch`, `adr: docs/adr`, `runbooks: docs/runbooks`;
     `artifacts.commit`; `work.ticket_pattern`; `protected_paths` (list); `risk.fintech` (bool);
     `workflows.enabled` = `[w0 … w10]`; `debug.services` = `services`, `debug.budget` =
     `{max_turns_total: 80, classification: 5, subagent: 20, fix_rounds: 3}`, `debug.allow_prod_log_access: false`;
     `knowledge.repo`; `integrations.jira_project_key`; `guard.extra_block_patterns: []`.
     - Values survive YAML-special characters (a `project_name` such as `py-svc: β #1` round-trips exactly).
     - Merge-friendly layout (ADR-0002 (c)): a blank line between top-level sections, and between any two keys
       of `commands` and of `paths` (no two of their value lines are adjacent).
     - It validates against `templates/project/schema/config.schema.json` for every stack (C29).

C29. **`templates/project/schema/config.schema.json`** — JSON Schema draft 2020-12 (`$schema` set,
     `Draft202012Validator.check_schema` passes). Required: `schema_version` (const 1), `kuanflow.min_version`
     (SemVer string), `project.{name,stack}`, `commands.{build,test,verify}` (non-empty strings),
     `paths.{work,wiki,scratch,adr,runbooks}`, `artifacts.commit` (enum), `protected_paths` (array of strings),
     `risk.fintech` (bool), `workflows.enabled` (array, items enum `w0`…`w10`, unique). Optional, typed when
     present: `commands.{single_test,lint}`, `work.ticket_pattern`, `debug.*`, `knowledge.repo`,
     `integrations.jira_project_key`, `guard.extra_block_patterns` (array of strings).
     `additionalProperties`: **true** inside the project-owned sections `project`, `commands`, `debug`,
     `knowledge`, `integrations`; **false** inside `kuanflow`, `paths`, `artifacts`, `work`, `risk`,
     `workflows`, `guard`, `debug.budget`; top level false except keys matching `^x-` (project extensions).

C30. **Patcher block bodies** — `templates/project/blocks/{agents.md,claude.md,gitignore,pr-template.md,
     worktreeinclude}.jinja` (D-P3-2: one `gitignore` body with conditions, not one file per mode). Each is a
     Jinja template of the block **body only** (no `kuanflow:begin/end` markers — the P4 patcher adds them);
     rendered with `jinja2.Environment(undefined=StrictUndefined, keep_trailing_newline=True)` and the answers of
     a rendered project, it renders without error and ends with exactly one `\n`.
     - `agents.md`: every line of PKG §6.5 between the markers, unchanged and in order, plus one added line
       (Q-16): `- No slash commands in your agent? Run the \`verify-agent-output\` skill (W8) instead.`
     - `claude.md`: exactly `@AGENTS.md\n`.
     - `gitignore`: engine lines `.kuanflow/config.local.yaml`, `.kuanflow/state.json`, `.kuanflow/scratch/`,
       `.kuanflow/cache/` always, and `CLAUDE.local.md`; `minimal` adds `kuan-workbench/work/*/questions.md`,
       `…/research.md`, `…/options.md`; `none` adds `kuan-workbench/`; `full` adds nothing. Comment lines
       `# Kuanflow — engine` / `# Kuanflow — output (artifacts.commit = <mode>)` as in PKG §6.2.
     - `pr-template.md`: PKG §18.8 in English:
       ```
       ## AI involvement
       - [ ] No AI used
       - [ ] AI assisted (suggestions, review)
       - [ ] AI wrote most of the code — passed W8

       Artifacts: `kuan-workbench/work/<TICKET>-<slug>/plan.md` · `review.md`
       Kuanflow version: v{{ kuanflow_version }}

       ## Verify evidence
       <!-- paste the verify command and its output, or a CI link -->
       ```
     - `worktreeinclude`: the three PKG §18.9 lines (`.kuanflow/config.local.yaml`, `CLAUDE.local.md`,
       `.env.local`).

### Knowledge repo template (T3.5) — `templates/knowledge-repo/` (Q-21)

C31. **`copier.yml`** — same `_min_copier_version`, `_subdirectory: template`, answers file and bans as C26.
     Questions: `org_name` (str, default `example-org`), `kuanflow_version` (str, default `""`).
     Rendered with `render(dst, {"org_name": …}, template="knowledge-repo")`: `.copier-answers.yml`, `README.md`,
     `postmortems/README.md`, `runbooks-shared/README.md`, `taxonomy.md`, `templates/postmortem.md` (PB §13.5,
     English), `templates/adr.md` (PB §13.6, English), `scripts/build-index.py`, `scripts/check-frontmatter.py`,
     `scripts/stale-wiki-check.sh` (all three executable, copied verbatim — no `.jinja`),
     `.github/workflows/knowledge-ci.yml` (on push + pull_request: checkout, setup-python, `pip install pyyaml`,
     run check-frontmatter, run build-index). Nothing else outside `.kuanflow/cache/`.
     - `taxonomy.md` has a `## Categories` section with exactly the 13 PB §7.5 categories, one per line as
       ``- `<category>` `` (`idempotency`, `concurrency/race`, `timeout/retry-storm`, `config`, `deployment`,
       `dependency-external`, `data-quality`, `schema/migration`, `capacity`, `precision/rounding`,
       `time/timezone/calendar`, `security/auth`, `observability-gap`).
     - `templates/postmortem.md` frontmatter passes `check-frontmatter.py` once `category`/`status` are set to
       valid values.

C32. **`scripts/check-frontmatter.py [--root DIR]`** (default cwd; Python 3.11 + PyYAML).
     Checks every `postmortems/**/*.md` except files named `README.md`. Each must start with a `---` YAML
     frontmatter block that is a mapping with: `id` non-empty string; `services` non-empty list of non-empty
     strings; `category` one of the taxonomy categories (parsed from `<root>/taxonomy.md` `## Categories`);
     `signatures` non-empty list of strings; `status` in `draft`, `approved`. One stderr line per problem,
     `<posix path relative to root>: <message>` (message names the field). Exit 0 all valid (also with no
     postmortems), 1 any problem, 2 when `taxonomy.md` is missing or has no categories.

C33. **`scripts/build-index.py [--root DIR] [--out FILE]`** — level-1 index. Writes JSON
     `{"version": 1, "entries": [...]}` (to stdout, or FILE), entries sorted by `path`:
     postmortems (same file set as C32) with valid frontmatter → `{"kind": "postmortem", "path", "id", "title",
     "date", "severity", "services", "category", "signatures", "status"}` (missing optional keys → `null`, dates
     as ISO strings); `runbooks-shared/**/*.md` except `README.md` → `{"kind": "runbook", "path", "title"}`
     (frontmatter `title`, else first `# ` heading, else file stem). Postmortems with invalid or missing
     frontmatter are skipped with one stderr warning each. Always exit 0 unless `--root` is not a directory (2).
     Deterministic output (same tree → same bytes).

C34. **`scripts/stale-wiki-check.sh <repo-path>`** (bash + git + python3 with PyYAML). For each
     `<repo>/kuan-workbench/wiki/*.md` whose frontmatter has `generated: true`: no `source_commit`, no
     `source_paths`, or a commit unknown to the repo → stdout `UNKNOWN <relpath>: <reason>`; any change in
     `source_paths` between `source_commit` and `HEAD` (`git diff --quiet <c> HEAD -- <paths>`) → stdout
     `STALE <relpath>`. Pages without `generated: true` are ignored. Never modifies files. Exit 0 nothing
     stale/unknown (also with no wiki dir), 1 any STALE/UNKNOWN, 2 usage error (no argument, or not a git work
     tree). `source_paths` may be a flow list (`[a, b]`) or a block list.

### Checks and packaging

C35. **`tests/check_schema.py`** — no args: (1) `Draft202012Validator.check_schema` on
     `templates/project/schema/config.schema.json`; (2) for every `tests/answers/*.yml`, `engine.render` the
     project template into a temp dir and validate `.kuanflow/config.yaml`. Exit 0 clean; 1 with one stderr line
     per error `<answers file or schema>: <json path>: <message>`. Added to `make verify` after check_skills.
C36. **Answers fixtures** `tests/answers/{java-maven,java-gradle,node,python,other}.yml` — `project_name` and
     `stack` only, except: `python.yml` has `project_name: "py-svc: β #1"`; `other.yml` has `use_orca: false`,
     `fintech: false`, `artifacts_commit: none`, `services: [a-svc, b-svc]`. None sets `kuanflow_version`.
C11a. **Wheel** (amends C11): also contains `kuanflow_cli/_content/VERSION`,
      `kuanflow_cli/_content/templates/project/copier.yml`, `…/templates/knowledge-repo/copier.yml`; and
      `engine.content_root()` inside an installed wheel resolves to `_content`.

## Tasks

| ID | Role | Files | Deps | Status |
|---|---|---|---|---|
| T3.0 | Coordinator | this plan (C23–C36, C11a); removed stale P1 agent worktrees | P2 | [x] |
| T3.1 | Test Eng | `tests/answers/*.yml`, `cli/tests/template/test_render_project.py`, `cli/tests/template/test_render_knowledge.py`, `cli/tests/template/test_blocks.py`, `cli/tests/test_engine_assemble.py`, `tests/check_schema.py`, `tests/test_check_schema.py`, `tests/bats/stale-wiki-check.bats`, `tests/test_packaging.py` (C11a only) | C23–C36 | [ ] |
| T3.2 | CLI Eng | `cli/src/kuanflow_cli/engine.py`, `pyproject.toml` (force-include of `VERSION` only) | T3.1 | [ ] |
| T3.3 | Template Eng | `templates/project/copier.yml`, `templates/project/template/**`, `templates/project/blocks/*.jinja` | T3.1 | [ ] |
| T3.4 | Template Eng | `templates/project/schema/config.schema.json` | T3.1 | [ ] |
| T3.5 | Template Eng (knowledge) | `templates/knowledge-repo/**` | T3.1 | [ ] |
| T3.6 | Coordinator | `Makefile` (check_schema step), CHANGELOG, VERSION `0.3.0-dev` | all | [ ] |

## Verify (phase exit)
`make verify` exit 0 (incl. `check_schema.py`); render tests green for 5 stacks; knowledge render + frontmatter +
index + stale-wiki bats green; RED of T3.1 recorded; adversarial review PASS.

## Evidence log
- (fill in)

## Decisions log
- D-P3-1: `lint_cmd` stack defaults (Q-11 adds the question; PKG gives no defaults): maven `spotless:check` (PKG
  §7.1 sample), gradle `spotlessCheck`, others `make lint`. node/python keep PKG §6.3 `make` defaults; the P4
  detector (Q-20) passes real commands as data.
- D-P3-2: one `gitignore` block body with `artifacts_commit` conditions instead of `gitignore-*` files.
- D-P3-3: `kuanflow_version` is filled by `engine.render()` from `VERSION` (copier.yml default `""`), so the
  template never hard-codes a version (Q-11). `VERSION` ships in the wheel (C11a).
- D-P3-4: scripts get mode 0755 in the synthetic repo regardless of source mode — resolves D-P2-6 without relying
  on the wheel keeping the exec bit.
- D-P3-5: knowledge-repo uses the same engine and cache path (`.kuanflow/cache/template-repo`), so
  `kuanflow upgrade` can treat it like a project later.

## Status (update before any context reset)
- T3.0 done. Next: T3.1 (Test Eng sub-agent), RED commit.
