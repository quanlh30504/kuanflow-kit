---
work: KF-003-p2-content
phase: P2 — Content source
parent_plan: kuan-workbench/work/KF-001-plan/plan.md
status: done — Gate P2 passed (2026-10-12)
---
# P2 — Content source

Sources: PKG = `docs/packaging.md`, PB = `docs/playbook.md`. Gate 0 answers (Q-04, Q-05, Q-07, Q-11, Q-17,
Q-25) apply. All runtime messages and content are English. All commands run as `uv run --locked …` (C7r).

## Contracts (tests are written against THESE, not against code)

### Guard scripts (T2.1 / T2.3) — `plugins/kuanflow/scripts/`

C12. **Common hook rules** (PKG §5.5, SCR-01). Each script is `bash`, executable (mode 100755 in git), reads one
     JSON object on stdin. Exit `2` = block, with one line on stderr starting `Blocked by kuanflow guard:`. Exit `0`
     = allow. Bad JSON, empty stdin, or a missing field → exit `0`. Without `python3` → exit `0` (fail open; doctor
     warns in P4). **Project root**: walk up from `$PWD` to the first directory holding `.kuanflow/`, else
     `git rev-parse --show-toplevel`, else `$PWD`. Config layers = `.kuanflow/config.yaml` then
     `.kuanflow/config.local.yaml`; PyYAML missing or a file that does not parse → that file is ignored.

C13. **`guard-bash.sh`** reads `tool_input.command`. Blocks (SCR-03), one rule each:
     | Rule | Block example | Allow example |
     |---|---|---|
     | B1 force push to main/master/release* | `git push --force origin main`, `git push -f origin release/1.2` | `git push --force origin feature/x` |
     | B2 direct push to main/master (ref is a whole token, `HEAD:main`, `refs/heads/main`) | `git push origin main`, `git push origin HEAD:master` | `git push origin feature/main-menu`, `git push origin fix/main-x` |
     | B3 kubectl/helm with prod context/namespace | `kubectl --context prod-eu get pods`, `helm upgrade x -n production` | `kubectl --context staging get pods` |
     | B4 psql/mysql/mongosh/redis-cli to prod | `psql -h db.prod.internal` | `psql -h localhost -U app` |
     | B5 `rm` recursive+force of `/`, `/*`, `~`, `~/`, `$HOME`, `${HOME}`, `.`, `..`, `./`, `../` (flags `-rf`, `-fr`, `-Rf`, `-r -f`…) | `rm -rf /`, `rm -fr ~`, `rm -rf $HOME`, `rm -rf .` | `rm -rf ./build`, `rm -rf target` |
     | B6 `drop database|schema|table` (any case) | `psql -c "DROP TABLE orders"` | `grep -r drop_log .` |
     | B7 reading `.env` / `.env.*` with cat/less/more/head/tail/cp/scp | `cat .env`, `cp .env.production /tmp/x` | `cat README.md`, `cat .envrc` |
     | B8 each `guard.extra_block_patterns[]` regex (Python `re.search`) from config + local; invalid regex ignored | pattern `terraform apply` blocks `terraform apply -auto-approve` | `terraform plan` |
     Normal commands pass (`./mvnw -q test`, `git status`, `git push origin feature/x`).

C14. **`guard-protected-paths.sh`** reads `tool_input.file_path` (relative paths resolve against `$PWD`). Globs =
     union of `protected_paths[]` from config + local. Blocks only when the path (relative to root) matches a glob
     **and the file already exists**; new files are allowed; paths outside the root are allowed. Glob semantics:
     `fnmatch` (`*` also matches `/`), and a leading `**/` also matches zero directories (`**/legacy/**` protects
     `legacy/a.java`). Paths with spaces, unicode and `[`/`]` work. The stderr line names the path and the glob.

C15. **`load-config.sh`** (SessionStart, PKG §18.3, SCR-02). Never exits non-zero, never writes to stderr in normal
     operation. No config and no local file → no output. Otherwise stdout:
     1. `## kuanflow v<ver>` — `<ver>` from `.kuanflow/manifest.json` `kuanflow_version`, else
        `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json` `version`, else `unknown`.
     2. `Effective config (later file overrides earlier):`, then for each existing layer `### .kuanflow/<file>` and
        its content in a ```` ```yaml ```` fence.
     3. If `kuanflow.min_version` (local overrides project) is newer than `<ver>`: a line starting `WARNING:` that
        contains both versions and `kuanflow upgrade`. SemVer order on `MAJOR.MINOR.PATCH`; with equal cores a
        prerelease is older than the release. Unknown/unparseable versions → no warning.
     4. Last line starts `Rules:` (PKG §18.3 text).

### Static checks (T2.2) — `tests/check_skills.py <plugin_dir>` (extends C5)

C16. Same CLI as C5 (no arg → 2, not a dir → 1, clean → 0, one stderr line per violation, `path[:line]: msg`). Rules:
     - S1 `skills/<d>/SKILL.md`: `name == <d>`; `description` non-empty string, ≤ 1024 chars.
     - S2 `agents/<f>.md`: `name == <f>`; non-empty `description`; `tools` present (comma string or YAML list),
       each tool in `Read, Grep, Glob, Bash, Write, Edit, WebFetch, WebSearch`. Read-only roles
       (`codebase-locator`, `codebase-analyzer`, `pattern-finder`, `adversarial-reviewer`, `rca-*`) must not have
       `Write` or `Edit`.
     - S3 `commands/<f>.md`: frontmatter with non-empty `description`.
     - S4 No hard-coded build command (`mvnw`, `gradlew`, `npm run`, `mvn` + whitespace) in any file under
       `skills/`, `agents/`, `commands/` — except inside a fenced code block whose opening fence is the first
       non-blank line after a `<!-- kuanflow:example -->` line.
     - S5 Banned patterns in every text file of the plugin, no exemption (Q-25): `ignore (all )?previous
       instructions` (any case); `verify=False`; `NODE_TLS_REJECT_UNAUTHORIZED=0`; `curl`/`wget` with `-k`,
       `--insecure` or `--no-check-certificate`; `curl`/`wget` with an `http(s)://` URL whose host is not a
       placeholder (`<…>`, `localhost`, `127.0.0.1`, `example.com|org|net` and their subdomains).

### Content (T2.4–T2.6, T2.8) — `plugins/kuanflow/`

C17. **Skills** — exactly these 10 dirs, with these side files:
     `daily-plan`, `clarify-requirements` (+`checklists/fintech-questions.md`), `write-spec` (+`templates/spec.md`),
     `research-solution`, `verify-agent-output`, `fintech-review`,
     `debug-incident` (+`scripts/collect_context.sh`, `schemas/context.schema.json`),
     `write-postmortem` (+`templates/postmortem.md`), `work-report`, `knowledge-gardening`.
     a. The first `##` heading of every SKILL.md is `## Before you start`. That section names
        `.kuanflow/config.yaml` and `.kuanflow/config.local.yaml`, lists the keys the skill needs, and says to
        stop and ask when a required key is missing.
     b. Verbatim (PKG §7.2 "verbatim where given"): for `verify-agent-output` (PB §8.4), `fintech-review` (§8.5),
        `debug-incident` (§8.6): frontmatter `name`/`description` equal the PB sample; every non-empty body line of
        the sample appears unchanged, in the same order (lines may be added between them).
     c. Skills that write into a work folder (`clarify-requirements`, `write-spec`, `research-solution`,
        `verify-agent-output`, `debug-incident`, `write-postmortem`) state the resolution order
        `KUANFLOW_WORK` → `work.ticket_pattern` (branch name) → `.kuanflow/state.json` → ask.
     d. `risk.fintech` is referenced by `clarify-requirements`, `write-spec`, `verify-agent-output`,
        `fintech-review`.
     e. `write-spec` and `write-postmortem` check `.kuanflow/templates/<file>` (project override) before their own
        template.
C18. **Agents** — exactly 9: `codebase-locator`, `codebase-analyzer`, `pattern-finder`, `test-writer`,
     `adversarial-reviewer`, `rca-timeline`, `rca-change-correlation`, `rca-code-path`, `rca-past-incident`.
     `codebase-analyzer`, `test-writer`, `adversarial-reviewer` are verbatim PB §8.7 (frontmatter `name`,
     `description`, `tools` equal; body lines as in C17b). Others derive from PB W3 / §6.4 and are read-only.
C19. **Commands** — exactly 12: `w0-daily`, `w1-clarify`, `w2-spec`, `w3-research`, `w4-plan`, `w5-implement`,
     `w6-test`, `w7-debug`, `w8-verify`, `w9-report`, `w10-capture`, `doctor`. Each has `description` and
     `argument-hint` and uses `$ARGUMENTS`. `w8-verify` is verbatim PKG §5.4 (C17b rule). Each `w*` command names
     `workflows.enabled` and stops when its id is not enabled. Delegation: w0→`daily-plan`, w1→`clarify-requirements`,
     w2→`write-spec`, w3→`research-solution`, w7→`debug-incident`, w8→`verify-agent-output`, w9→`work-report`,
     w6→`test-writer`. `w4-plan`, `w5-implement`, `w6-test`, `w10-capture` are self-contained (Q-04): they name the
     Superpowers skill(s) only as "if installed" and carry the rules themselves (w4: phase template with
     `Verify:` and `[ ] todo`; w5: never modify/skip/delete existing tests; w6: every AC has a test; w10: the PB W10
     event table). `doctor` runs `kuanflow doctor` when on PATH, else does the Q-17 checks by hand.
C20. **No hard-coded project paths** in skills/agents/commands: no `kuan-workbench/`, `docs/adr`, `docs/runbooks`
     literals (use `paths.*`). Every backticked config key (`commands.*`, `paths.*`, …) used in content is a key of
     PKG §7.1 or `guard.extra_block_patterns` (Q-11), and appears in the README key table (C22).
C21. **`debug-incident` collector** (Q-07, T2.7) —
     `scripts/collect_context.sh --id <ID> [--service S]… [--log FILE]… [--trace FILE]… [--changes FILE]
     [--metrics FILE] [--symptom TEXT] [--severity SEVn] [--source alert|ticket|report|manual]
     [--similar INC]… [--root DIR]`.
     - `--id` required, `^[A-Za-z0-9][A-Za-z0-9._-]*$`; usage errors → exit 2.
     - Missing/unreadable input file → exit 1. Output dir = `<root>/<paths.scratch>/<ID>/` (default
       `.kuanflow/scratch`); a `paths.scratch` that resolves outside `<root>/.kuanflow/` → exit 1. Writes ONLY
       `context.json` there; prints its path on stdout.
     - `--log`: lines with `ERROR`/`Exception`/`FATAL` → `symptom.error_signatures` (unique, first 20) and
       `log_excerpts`. `--trace`: JSON object or list in the `samples[]` shape. `--changes` → `changes_in_window`,
       `--metrics` → `metrics` (JSON objects).
     - Masking before writing, on every string from inputs/args: e-mail → `<email>`; phone (`+84…`/`0…`, 10–11
       digits) → `<phone>`; `account_no|account_number|accountNo|acct` `=`/`:` value → `<account_no>`;
       `id_number|idNumber|national_id|cccd|cmnd|passport` value → `<id_number>`; standalone runs of 9–19 digits →
       `<number>`. `redaction.applied = true`, `redaction.fields` lists the four PB field names.
     - Size ≤ 51200 bytes: drop `log_excerpts` from the end, then `samples`, set `budget.truncated: true`; still too
       big → exit 1, nothing written.
     - Output validates against `schemas/context.schema.json` (JSON Schema 2020-12, derived from PB §6.5; the PB
       sample validates). No network tool is used (no `curl`, `wget`, `nc`, `ssh`, sockets).
C22. **`plugins/kuanflow/README.md`** names every skill, agent and command, and has a config-key table listing
     every key used in content (C20).

## Tasks

| ID | Role | Files | Deps | Status |
|---|---|---|---|---|
| T2.0 | Coordinator | this plan (contracts C12–C22) | P1 | [x] |
| T2.1 | Test Eng | `tests/bats/{guard-bash,guard-protected-paths,load-config,collect-context}.bats`, `tests/bats/helpers/common.bash` | C12–C15, C21 | [x] |
| T2.2a | Test Eng | `tests/test_check_skills.py`, `tests/test_plugin_content.py` | C16–C22 | [x] |
| T2.2 | Release/CI | `tests/check_skills.py` (S1–S5) | T2.2a | [x] |
| T2.3 | Script Eng | `plugins/kuanflow/scripts/{load-config,guard-bash,guard-protected-paths}.sh` | T2.1 | [x] |
| T2.4 | Content Eng | `plugins/kuanflow/skills/**` (except `debug-incident/scripts/`) | T2.2a | [x] |
| T2.5 | Content Eng | `plugins/kuanflow/agents/*.md` | T2.2a | [x] |
| T2.6 | Content Eng | `plugins/kuanflow/commands/*.md` | T2.4 | [x] |
| T2.7 | Script Eng | `plugins/kuanflow/skills/debug-incident/scripts/collect_context.sh` | T2.1, schema | [x] |
| T2.8 | Content Eng | `plugins/kuanflow/README.md` | T2.4–T2.6 | [x] |

Run inline by the coordinator (no sub-agents this phase; the user did not ask for them).

## Fix round 1 (after review FAIL — see review.md F1–F4)

Contract amendments (tests are written against these):

C13a. **Wrapped commands** — every word of a command line that contains whitespace (e.g. the argument of
      `bash -c`, `sh -c`, `eval`, `ssh host "…"`) is also checked as a command line of its own, up to 3 levels
      deep. `bash -c "git push --force origin main"`, `sh -c 'rm -rf /'`, `eval "git push origin main"` block.
C13b. **B5 amended** — a recursive `rm` (`-r`, `-R`, `--recursive`) of a B5 target blocks with or without `-f`.
      `rm -r ~` blocks; `rm -r ./build` is allowed.
C12a. **No imports from the project** — with a `json.py` and a `yaml.py` in the working directory that write a
      marker file, none of the four scripts runs them (no marker) and the guards still decide correctly.
C13c. Explicit cases: `git push origin +main` blocks (force refspec); `more .env` blocks.

| ID | Role | Files | Status |
|---|---|---|---|
| FX1.0 | Test Eng | `tests/bats/guard-bash.bats`, `tests/bats/{guard-protected-paths,load-config,collect-context}.bats` (C12a) | [x] |
| FX1.1 | Script Eng | `plugins/kuanflow/scripts/guard-bash.sh` (C13a, C13b) | [x] |

## Verify (phase exit)
`make verify` exit 0 (check_skills now runs the full rules on real content); bats green for every guard rule;
RED of T2.1/T2.2a recorded; adversarial review PASS; reviewer compares skills against PB text.

## Evidence log
- RED (e94863a): pytest `195 failed, 21 passed, 1 skipped, 7 errors`; bats `102 not ok, 3 ok`.
- GREEN (358713f): `make verify` exit 0 — `775 passed`, bats `1..105` ok, check_skills and check_versions silent.
- Review (review.md): FAIL — 22 mutations, 5 survived; `bash -c`/`eval` bypass. Fix round 1: RED (dd111d1)
  5 bats failing; GREEN after FX1.1: `make verify` exit 0, bats `1..118`; all survivors + M23 killed.
- Test fixes after RED, both recorded: 6f1556c (bats stderr temp file; C17e made stricter), fix-round helper
  `json_field` now `python3 -I` (it imported the planted module).

## Decisions log
- D-P2-1: Regex tightening vs PKG §18.4 sample (C13 B2/B5/B7): whole-token branch match (PKG sample blocks
  `git push origin fix/main`), `rm -fr`/`-r -f` variants, `more` added to B7. Behaviour of every PKG example is kept.
- D-P2-2: `load-config.sh` compares versions with SemVer core + prerelease (PKG sample crashes on `0.2.0-dev` and
  would print a false warning). `min_version` read with PyYAML, regex fallback.
- D-P2-3: Skill/command content is English (repo rule); PB templates (§13.2, §13.5) are translated, structure kept.
- D-P2-4: Content additions beyond PB/PKG → Q-31 (state.json format, fintech skip, test map, workflows gate).
- D-P2-5: guard-bash scans quoted words as commands (C13a) → false positives on quoted text, as in the PKG
  sample → Q-29.
- D-P2-6: Note for P3/P4: the wheel must keep the executable bit of the scripts, or the installer must
  `chmod +x` them (SCR-06); not checked in P2.

## DoD (phase exit)
- [x] `make verify` exit 0 (pytest 775, bats 118, check_skills clean on real content, check_versions).
- [x] RED recorded for T2.1/T2.2a and FX1.0; GREEN recorded.
- [x] Review FAIL → fix round 1 → re-review PASS (review.md).
- [x] VERSION `0.2.0-dev`; `check_versions.py --tag v0.2.0-dev` exit 0; tag `v0.2.0-dev` (local, not pushed).
- [x] Gate P2: Q-29 → A, Q-30 accepted, Q-31 accepted (all recommendations).

## Status (update before any context reset)
- P2 DONE. Gate P2 passed (all recommendations). Tag `v0.2.0-dev` local only.
- NEXT (only when the user asks): P3 (KF-004) templates — tests first; remember D-P2-6 (exec bit).
