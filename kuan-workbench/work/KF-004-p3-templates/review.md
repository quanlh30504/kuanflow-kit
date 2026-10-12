# Review — KF-004 P3 Templates — `8fc26d8..fddc5a5`

Reviewer: Adversarial Reviewer (sub-agent; did not write the code). Mutations replayed one at a time in a
scratch clone reset to HEAD before each (`review-p3/mutate.py` + `run.sh` in the session scratchpad); oracle =
P3 pytest subset, `bats tests/bats/stale-wiki-check.bats`, `tests/check_schema.py`, and for any survivor the full
`pytest` + full `bats tests/bats`. Nothing in the repo changed except this file.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Full verify suite | PASS | `make verify` exit 0: ruff clean, `1053 passed`, bats `1..138` all ok, check_skills / check_schema / check_versions silent. |
| 2 | RED before GREEN | PASS | Re-run at 4e6ddba in a scratch clone: P3 pytest `40 failed, 15 passed, 234 errors`; stale-wiki bats `20 not ok` — matches the commit message. |
| 3 | Tests changed after RED | PASS | `git diff 4e6ddba fddc5a5 -- tests cli/tests` is empty. |
| 4 | Contract → test mapping (mutation) | **FAIL** | 60 mutants, 1 equivalent (M51), **53/59 killed (90 %)**. Survivors: M17, M19, M29, M30, M45, M55 (table below). |
| 5 | C23–C36 by reading | PASS with gaps | Code matches every contract clause I could check. The gaps are in the contracts: C28 (merge layout, F2), C31 (cache not ignored, F3), C26 (no list validation, F4). |
| 6 | ADR-0002 behaviour | PASS | `_src_path: .kuanflow/cache/template-repo` (relative), `_commit: v<ver>`, HEAD on a lightweight tag, `unsafe=False`. The template has no `_tasks`, `_migrations` or `_jinja_extensions`, and the answers-file template is shipped. |
| 7 | Real 3-way update probe | **PARTIAL** | Assembled v0.3.0+v0.4.0 and ran `run_update(vcs_ref="v0.4.0", defaults=True, overwrite=True, conflict="inline")`. **A**: local `commands.verify` vs upstream `commands.build` → merged cleanly, local edit kept. **B**: local `debug.allow_prod_log_access` vs upstream `debug.budget` → **conflict** (`UU`, markers). **C**: local `debug.services` vs upstream `debug.budget` → **conflict**. See F2. |
| 8 | Injection via answers | PASS | `project_name` with `\n`, `{{ 7*7 }}`, `{% raw %}`, U+2028 and `\`; a `build_cmd` with a newline plus a fake key; `services` with `\n` and `{{ }}`; and `jira_project_key` with `'"\` all round-trip exactly through config.yaml and `.copier-answers.yml`. Nothing is re-rendered, and the result still validates. **But** a scalar where a list is expected is accepted silently (F4). |
| 9 | Knowledge scripts hygiene | PASS | stale-wiki-check worked with a repo path, page name and source_paths that contain spaces and Vietnamese characters. `python3 -I` holds: a `yaml.py` planted in cwd did not run. There are no network calls. It never writes (bats + M54). YAML is parsed with `safe_load` / `BaseLoader` only. |
| 10 | Wheel (C11a) | PASS | Built with hatchling in a scratch copy. `_content/` holds `VERSION`, both `copier.yml`, the Jinja-named files and the `.gitkeep`s, exactly matching `git ls-files templates plugins VERSION`. Scripts are `0755` in the zip. `content_root()` from an installed wheel is covered by `test_c11a_content_root_in_installed_wheel` (M16 killed). |
| 11 | Content quality | PASS | English only (non-ASCII: `§ · – — →`). The agents block is PKG §6.5 verbatim, with the Q-16 line before the last rule. PR template = §18.8; worktreeinclude = §18.9. Knowledge `templates/postmortem.md` and `templates/adr.md` follow the PB §13.5/§13.6 frontmatter and section lists 1:1. The READMEs are useful and name the CLI commands. |

### Mutation results

| ID | Mutation | Result | Killed by |
|---|---|---|---|
| M01 | drop `chmod(0o755)` | killed | test_c27_scripts_identical_and_executable |
| M02 | drop `GIT_CONFIG_GLOBAL` | killed | test_c24_user_global_git_config_ignored |
| M03/M03b | drop fixed author / committer date | killed | test_c24_commit_metadata |
| M04/M05 | skip ascending check / allow equal | killed | test_c24_invalid_versions |
| M06 | no cwd restore | killed | test_c25_cwd_restored_after_success |
| M07 | `kuanflow_version` not defaulted | killed | test_c31_answers_file, check_schema |
| M08 | mutate caller `data` | killed | test_c25_render_basic |
| M09 | overwrite caller `kuanflow_version` | killed | test_c25_caller_kuanflow_version_kept |
| M10 | release sorts before prerelease | killed | test_c24_prerelease_before_release_is_ascending |
| M11 | annotated tag | killed | test_c24_commit_metadata |
| M12 | dest not removed first | killed | test_c24_dest_existing_repo_replaced |
| M13 | worktree not cleared between versions | killed | test_c24_two_versions |
| M14 | `unsafe=True` | killed | test_c25_run_copy_call |
| M15 | absolute `_src_path` | killed | test_c31_answers_file |
| M16 | `content_root` ignores `_content` | killed | test_c11a_content_root_in_installed_wheel |
| **M17** | **inherit `GIT_*` env (no scrub)** | **survived** | — (F1) |
| M18 | VERSION not stripped | killed | test_blocks, check_schema |
| **M19** | **template check after `rmtree(dest)`** | **survived** | — (F5) |
| M20 | drop `orca.yaml` from `_skip_if_exists` | killed | test_c26_skip_if_exists |
| M21/M24 | gradle verify / node lint default changed | killed | test_c26_stack_default_answers |
| M22 | add `_tasks` | killed | render error in every render test, check_schema |
| M23 | `fintech` default false | killed | test_c26_question_types_and_defaults |
| M25/M28 | remove blank line in `commands` / between sections | killed | test_c28_blank_line_* |
| M26 | unquoted `project_name` | killed | test_c28_config_content[python], check_schema |
| M27 | drop `guard` section | killed | test_c28_config_content |
| **M29** | **`knowledge.repo: "{{ knowledge_repo }}"`** | **survived** | — (F5). The first run reported a full-pytest kill, but it overlapped with my probe; re-run: `1053 passed`. Baseline 3× green. |
| **M30** | **`jira_project_key: '{{ jira_project_key }}'`** | **survived** | — (F5) |
| M31–M37 | schema: open `paths` / `debug.budget`, close `knowledge`, drop `verify` required, SemVer pattern, `uniqueItems`, `^x-` | all killed | test_c29_* |
| M38–M42 | blocks: drop a PKG line, gitignore `none`/`minimal`, PR `v` prefix, `.env.local` | all killed | test_blocks |
| M43/M44/M46/M47 | category check off, README checked, empty `services` accepted, empty taxonomy → 0 | all killed | test_c32_* |
| **M45** | **`STATUSES` gains `published`** | **survived** | — (F5) |
| M48–M50 | index shuffled, invalid postmortem kept, runbook README kept | all killed | test_c33_* |
| M51 | `ensure_ascii=True` in the index JSON | equivalent | Same parsed JSON; the contract only asks for determinism. |
| M52–M54, M56–M58 | stale-wiki ignores source_paths, compares worktree, writes a file, always exit 0, checks non-generated pages, loader swap | all killed | stale-wiki-check.bats |
| **M55** | **stale-wiki drops `python3 -I`** | **survived** | — (F6) |
| M59 | knowledge `org_name` default | killed | test_c31_questions |

## Findings

- **F1 — med — The `GIT_*` env scrub in `engine._git_env` has no test (M17), and without it the engine writes
  into the user's repo.** I demonstrated it: with M17 applied, `GIT_DIR=<victim>/.git assemble_template(...)`
  added a commit and the tag `v0.2.0` to the *victim* repo. That is exactly what happens when `kuanflow` runs
  from a git hook. The real code is safe, but nothing protects it.
  *Fix:* none needed in code. *Test:* `test_c24_inherited_git_env_ignored` sets `GIT_DIR`, `GIT_WORK_TREE`
  and `GIT_INDEX_FILE` (monkeypatch env) to a second repo, calls `assemble_template`, then asserts that the
  second repo's HEAD, tags and index are unchanged and that `dest` has tag `v<ver>`.

- **F2 — med — `.kuanflow/config.yaml` is not merge-friendly in `debug` (probes B and C conflict).**
  `debug.services`, `debug.budget` and `debug.allow_prod_log_access` sit on adjacent lines. A user who lists
  their services (the normal case) gets an inline conflict on any upgrade that changes a budget default. The
  same happens with `allow_prod_log_access`. `budget` is a flow mapping on one line, so tuning any one budget
  value also conflicts with any upstream change to another. C28 only requires blank lines in `commands` and
  `paths`. The implementation satisfies the contract; ADR-0002 (c) ("separate the user-editable keys") does not
  hold.
  *Fix (amend C28):* put a blank line between every two keys of `debug`. Render `budget` as a block mapping with
  a blank line between its keys. Consider `project.name` / `project.stack` too.
  *Test:* extend `test_c28_blank_line_between_keys` to `debug` and `debug.budget`. Add
  `test_c28_three_way_update_no_conflict`, a parametrized real `copier.run_update` over (local key, upstream key)
  pairs: `commands.verify`/`commands.build`, `debug.services`/`debug.budget.max_turns_total`, and
  `debug.allow_prod_log_access`/`debug.budget`. Assert no `git ls-files -u` entries. This is also the
  "(b)/(c)/(f) on every Copier bump" integration test that ADR-0002 asks for, and that P3 does not have yet.

- **F3 — med — A rendered knowledge repo leaves `.kuanflow/cache/template-repo` (a nested git repo) un-ignored.**
  After `render(..., template="knowledge-repo")` and `git init`, `git status` shows `?? .kuanflow/`. `git add -A`
  then records the cache as an embedded repo (gitlink). Any later `kuanflow upgrade` is refused because the tree
  is dirty (ADR-0002 (d)). C31 lists the exact tree and has no `.gitignore`. D-P3-5 reuses the cache path, but no
  rule ignores it in this repo type, and C30's gitignore block exists for projects only.
  *Fix (amend C31):* ship `templates/knowledge-repo/template/.gitignore` with `.kuanflow/cache/` (and `index.json`,
  which CI builds). Alternatively, P4 applies the gitignore patcher to knowledge repos too, but the contract has
  to say which.
  *Test:* `test_c31_cache_ignored` renders into a fresh `git init` dir, then asserts that
  `git status --porcelain --untracked-files=all` contains no path under `.kuanflow/cache/`.

- **F4 — med — Scalar or mapping answers for `protected_paths` / `services` are silently split into characters or keys.**
  `protected_paths: "src/**"`, the obvious single-glob answer (e.g. from `--data`), renders as
  `["s","r","c","/","*","*"]`. A `*` entry turns `guard-protected-paths` into "protect every file". The result
  still validates against the schema. `services: {a: 1}` renders `["a"]`.
  *Fix:* add a Copier `validator:` (plain Jinja; allowed under `unsafe=False`) to both `yaml` questions, e.g.
  `{% if protected_paths is string or protected_paths is mapping or (protected_paths | select('string') | list | length) != (protected_paths | length) %}must be a list of strings{% endif %}`.
  Optionally coerce a string into a one-item list in the CLI (P4). Amend C26.
  *Test:* `test_c26_list_answers_validated[protected_paths|services × "src/**"|{"a":1}|[1]]` — `render` raises
  (a Copier `ValueError`), and no `.kuanflow/config.yaml` is written.

- **F5 — low — Test gaps behind survivors M19, M29, M30, M45.**
  (a) `test_c28_yaml_special_values_round_trip` uses values that survive naive quoting for `knowledge_repo` (no
  `"`) and `jira_project_key` (no `'`). Use one hostile value (`a"b'c\d: #e`) for *every* str answer.
  (b) Add `unknown-template` to `test_c24_invalid_versions_leave_existing_dest`.
  (c) In `test_c32_invalid_value`, add `status: published` and `status: Approved`, or assert the message lists
  exactly `draft, approved`.

- **F6 — low — The `python3 -I` isolation in `stale-wiki-check.sh` has no test (M55).** I checked manually: a
  `yaml.py` planted in cwd does not run. *Test:* a bats case that runs the script from a dir containing a
  `yaml.py` that writes a marker; the marker must not exist (same pattern as P2 C12a).

- **F7 — low — Non-ASCII answers are written as `\uXXXX` escapes in config.yaml**
  (`name: "Dịch vụ lệnh"`). They round-trip, but this file is meant to be edited by people.
  *Fix:* `to_json(ensure_ascii=False)` is available in Copier's filter set. Keep U+2028/U+2029/U+0085 escaped,
  for example by post-replacing them, because YAML treats them as line breaks. *Test:* the `python` fixture
  config text contains `β` literally, and the U+2028 round-trip still passes.

- **F8 — info, for P4/P6, no P3 change needed.**
  (a) `render()` into a dir that already has a different rendered file raises
  `InteractiveSessionError: Consider using --overwrite`; the P4 `init` must pre-check or pass `overwrite`.
  (b) PKG §18.9 generates `.worktreeinclude` only when `use_orca`; the block body has no condition, so the
  patcher must apply it conditionally.
  (c) `project_name: ""` renders a config that fails the schema (`minLength 1`). A `validator` would catch it at
  render time.
  (d) `source_paths` entries are git pathspecs (`:(exclude)x` and globs are interpreted); document this, or
  prefix with `:(literal)`.
  (e) T3.6 (CHANGELOG, VERSION `0.3.0-dev`) is not done yet.

## "What would make me reject this phase even though verify is green?"
1. A safety property whose absence corrupts the user's repo, with no test: yes, F1 (proven with a mutant).
2. A template layout that the ADR says must avoid upgrade conflicts, but conflicts on the most common
   customisation (`debug.services`): yes, F2.
3. A rendered repo that cannot be upgraded (dirty, embedded repo): yes, F3.
4. Plausible user input that silently turns into a dangerous config (`*` protected path): yes, F4.
5. Content that contradicts PKG/PB, or non-English text: checked, none found (rows 10, 11).

## Verdict: FAIL — fix F1–F4 (F5–F7 are cheap to fold into the same round), then re-review.
