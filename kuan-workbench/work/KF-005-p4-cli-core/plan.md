---
work: KF-005-p4-cli-core
phase: P4 — CLI core
parent_plan: kuan-workbench/work/KF-001-plan/plan.md
status: in progress
---
# P4 — CLI core

Sources: PKG = `docs/packaging.md` (§6.1–6.5, §9.2–9.8, §9.10, §10.5, §12.5, §18.2), research.md (CMD-01..08,
CMD-18..25, DET-01..07, MAN-01..07, OWN-01..06, PER-01..06, TST-08..11, 15, 16), ADR-0002. Gate 0 answers Q-08,
Q-13..Q-18, Q-20, Q-22 and Gate P3 answers Q-32 (fix round 2), Q-34 (root handling) apply. All content and
messages are English. All commands run as `uv run --locked …` from the repo root.

Execution: sub-agents (user asked for multi-agent). Agents work in the main tree on **disjoint files** and do not
commit; the coordinator commits after each step. Order: T4.0 (this brief + `errors.py`) →
{T4.1a ∥ T4.1b ∥ T4.1c} tests RED → {T4.2 ∥ T4.3 ∥ T4.4} → {T4.5 ∥ T4.6} → GREEN → adversarial review → fix
rounds → DoD.

Scope note: no agent adapters and no `upgrade` in P4 (P5/P6). `--agent` with a value is an error (C47). The JSON
and TOML key patchers are built and unit-tested now; P5 adapters use them.

## Contracts (tests are written against THESE, not against code)

### General

C36a. **Errors** — `cli/src/kuanflow_cli/errors.py` (written by the coordinator in T4.0): `KuanflowError(Exception)`
      with `exit_code = 1`; subclasses `RootError`, `DirtyTreeError` (attribute `paths: list[str]`), `AnswersError`,
      `ManifestError`, `PlanError`, `PlanConflictError(PlanError)`, `BlockError`, `KeysError`, `RenderError`,
      `NotInstalledError`. Every command catches `KuanflowError` and prints `error: <message>` to **stderr**, exit
      `exit_code`, no traceback.
C36b. **Exit codes** (CMD-22) — `0` ok · `1` any error, including CLI usage errors (unknown option/command, missing
      argument; Click/Typer's default 2 must be mapped to 1) · `2` and `3` reserved for `upgrade` (P6), never
      returned in P4.
C36c. **Time** — every timestamp (manifest, promote date, backup dir name) comes from `kuanflow_cli.clock.now()`:
      env `KUANFLOW_NOW` (ISO-8601 with offset, e.g. `2026-11-03T09:00:00+07:00`) when set, else
      `datetime.now().astimezone()`; truncated to seconds. Manifest/ISO form `2026-11-03T09:00:00+07:00`
      (`isoformat(timespec="seconds")`), date form `2026-11-03`, backup form `20261103T090000`.
C36d. **Git** — every git subprocess the CLI runs uses an env without inherited `GIT_*` variables (like
      `engine._git_env`, but without the fixed identity) and `-C <dir>`; the CLI never commits, stages or changes
      git config. Test files use unique basenames repo-wide (pytest runs without `__init__.py`), and tests import
      CLI modules lazily (`importlib` inside tests/fixtures) so a missing module fails tests, not collection.

### Fix round 2 for P3 (Q-32) — `templates/project/template/.kuanflow/config.yaml.jinja`

C28c. Blank line between `project.name` and `project.stack`; the C28a real 3-way update test also covers the leaf
      pair (`project.name`, `project.stack`) with no unmerged path.
C28d. These characters are written `\u`/`\U`-escaped in `config.yaml` (never raw) and still round-trip exactly:
      U+00AD, U+061C, U+180E, U+200B–U+200F, U+202A–U+202E, U+2060–U+2064, U+2066–U+206F, U+FEFF, U+FFF9–U+FFFB,
      U+FFFE, U+FFFF, U+E0001, U+E0020–U+E007F. A lone surrogate either round-trips or `render()` raises (no
      `config.yaml` with a broken value).
C28e. Literal non-ASCII (C28b) holds for **every** string answer written to `config.yaml`: `project_name`, each
      `*_cmd`, `ticket_pattern`, every `protected_paths` and `services` item, `knowledge_repo`, `jira_project_key`.

### Root (T4.2) — `cli/src/kuanflow_cli/root.py`

C37. `git_toplevel(path) -> Path | None` — resolved `git rev-parse --show-toplevel` run in `path`; `None` when `path`
     is not inside a git work tree. `find_root(start, explicit=None) -> Path`:
     - `explicit` given → `explicit.resolve()`; must be an existing directory inside a git work tree, else
       `RootError`.
     - else: `top = git_toplevel(start)`; `None` → `RootError("not inside a git repository")`. Walk from
       `start.resolve()` up to and including `top` (never above it); the first directory that contains the
       **file** `.kuanflow/manifest.json` is the root. None found → `top`.
       (A `~/.kuanflow/` user directory or a `.kuanflow/` without a manifest never counts.)
     - Every command resolves its root this way from the process cwd, with `--root` as `explicit`, and all relative
       paths in CLI output are relative to that root (posix form).

### Detector (T4.2) — `cli/src/kuanflow_cli/detect.py`

C38. `detect(root) -> Detection` (frozen dataclass: `answers: dict[str, Any]`, `agents: list[str]`,
     `notes: list[str]`). Reads files under `root` only; never runs a command; never fails (unreadable or invalid
     files are skipped with a note).
     - `project_name` = `root.name`.
     - Stack, first match wins:

       | Signal (in `root`) | stack | `<x>` |
       |---|---|---|
       | `pom.xml` or `mvnw` | `java-maven` | `./mvnw` if `mvnw` exists, else `mvn` |
       | `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts` or `gradlew` | `java-gradle` | `./gradlew` if `gradlew` exists, else `gradle` |
       | `package.json` | `node` | package manager `<pm>`: `pnpm` if `pnpm-lock.yaml`, `yarn` if `yarn.lock`, else `npm` |
       | none | `other` | — |

       java-maven: `build_cmd` `<x> -q -DskipTests package`, `test_cmd` `<x> -q test`, `verify_cmd` `<x> -q verify`,
       `single_test_cmd` `<x> -q -Dtest={test} test`, `lint_cmd` `<x> -q spotless:check`.
       java-gradle: `<x> assemble`, `<x> test`, `<x> check`, `<x> test --tests {test}`, `<x> spotlessCheck`.
       node (Q-20): `test_cmd` `<pm> test`; `single_test_cmd` `<pm> test -- {test}`; `build_cmd` `<pm> run build`
       only if `scripts.build` exists; `lint_cmd` `<pm> run lint` only if `scripts.lint` exists; `verify_cmd`
       `<pm> run verify` if `scripts.verify` exists, else the `test_cmd`. Keys not set here are omitted (template
       default applies). Invalid `package.json` → stack still `node`, no script-based keys, a note.
       other: no command keys.
     - `protected_paths` = `["src/main/resources/db/migration/**", "**/legacy/**"]` if the directory
       `src/main/resources/db/migration` exists, else `["**/legacy/**"]` (DET-04).
     - `use_orca` = `orca.yaml` exists in root or `shutil.which("orca")` (DET-06).
     - `agents` (DET-05), sorted unique: `claude` if `.claude/` or `which("claude")`; `codex` if `.codex/` or
       `which("codex")`; `opencode` if `.opencode/` or `which("opencode")`; `kiro` if `.kiro/` or
       `which("kiro-cli")`. Lookups go through `detect.shutil.which` (tests monkeypatch it).
C39. `collect_answers(root, *, template="project", data_file=None, personal=False) -> dict[str, Any]` — layers, later
     wins: `detect(root).answers` (project template only) → existing `<root>/.copier-answers.yml` (keys not starting
     with `_`, minus `kuanflow_version`) → `data_file`. `personal=True` forces `artifacts_commit = "none"`.
     `data_file` must be a YAML mapping whose keys are questions of `templates/<template>/copier.yml` (keys not
     starting with `_`), excluding `kuanflow_version`; otherwise (missing file, not a mapping, unknown key, YAML
     error) `AnswersError` naming the file and key. Returned dict never contains `kuanflow_version`.

### Manifest (T4.2) — `cli/src/kuanflow_cli/manifest.py`

C40. File `.kuanflow/manifest.json`. Key order exactly as below; `json.dumps(indent=2, ensure_ascii=False) + "\n"`.
     ```json
     {
       "manifest_version": 1,
       "kuanflow_version": "0.4.0-dev",
       "template": "project",
       "installed_at": "2026-11-03T09:00:00+07:00",
       "updated_at": "2026-11-04T10:00:00+07:00",
       "mode": "project",
       "agents": [],
       "source": "git+https://github.com/<org>/kuanflow.git@v0.4.0-dev",
       "files": [ … ]
     }
     ```
     - `updated_at` is present only after a later run changed something (Q-22); `installed_at` never changes.
     - `source` = env `KUANFLOW_SOURCE` (else `git+https://github.com/<org>/kuanflow.git`) + `@v<kuanflow_version>`.
     - `files` sorted by `path`; one entry per path; fields in this order:
       - `template-managed` | `merge-required` | `local-owned`: `{"path", "owner", "sha256"}` (sha256 hex of the
         bytes written).
       - `managed-block`: `{"path", "owner", "block": "kuanflow", "sha256", "created"}` — sha256 of the block
         **body** (C42), `created` = the file did not exist before Kuanflow wrote it.
       - `managed-keys` (P5): `{"path", "owner", "keys": {"<dotted key>": "<sha256>"}, "created"}` (C45).
       - optional `"agent"` last (P5).
       - The personal-mode exclude file has `"path": "git:info/exclude"` (C46).
     API: dataclasses `Manifest`, `FileEntry`; `read(root) -> Manifest | None` (None when absent);
     `ManifestError` for invalid JSON, `manifest_version != 1`, missing/mistyped field, unknown owner;
     `dumps(m) -> str`; `write(root, m)`; `sha256_bytes(b) -> str`; `diff(old, new) -> dict` with keys
     `added`, `removed`, `changed` (sorted path lists). `read(write(m))` round-trips; `dumps` is deterministic.

### Change plan (T4.3) — `cli/src/kuanflow_cli/plan.py`

C41. `Change(path, before, after, mode=None, reason="")` — `path` posix, relative to root; `before`/`after`: bytes or
     `None` (absent); `after=None` = delete; `mode` `0o755`/`0o644` or `None` (new file → `0o644`, existing → keep).
     `Plan`: `add(change)` (a no-op change — same bytes and mode — is dropped), `extend`, iteration in path order,
     `len`, `paths()`.
     - `diff_text(plan) -> str`: per change in path order a unified diff (3 context lines) with headers
       `--- a/<path>` / `+++ b/<path>` (`/dev/null` for create/delete); bytes decoded UTF-8 with `replace`; a mode
       change is shown as git does (`old mode 100644` / `new mode 100755`). Empty plan → `""`.
     - `apply(plan, root, *, backup=True) -> Path | None`:
       1. Validate all first, write nothing on failure: a path that is absolute, contains `..`, or has a symlink
          as any existing component (or is one) → `PlanError`; a `before` that does not match the current disk
          bytes (or existence) → `PlanConflictError` naming the path.
       2. If `backup` and the plan modifies or deletes any existing file: copy each such file (bytes) to
          `<root>/.kuanflow/cache/backup/<clock backup form>[-N]/<path>` before changing it; return that dir,
          else `None`.
       3. Writes are atomic (temp file in the same directory + `os.replace`); parent dirs created; mode applied.
          Deletes remove the file, then each parent directory that became empty, never `root` itself.

### Patchers (T4.3) — `cli/src/kuanflow_cli/patchers/`

C42. **`managed_block.py`** — styles: `html` → begin line
     `<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->`, end line `<!-- kuanflow:end -->`;
     `hash` → `# kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here)`, `# kuanflow:end`.
     `style_for(path)` = `html` for `*.md`, else `hash`.
     - Recognition: a begin is a line whose text (trailing whitespace/`\r` stripped) starts with
       `<!-- kuanflow:begin` (html) / `# kuanflow:begin` (hash); an end is a line equal to the end marker after the
       same stripping. Body = the lines strictly between them (with their newlines).
     - `find(text, style) -> Block | None` (`start`, `end` char offsets covering begin line through end line incl.
       its newline; `body`). Two begins, begin without end, end without begin, or end before begin → `BlockError`.
     - `render_block(body, style) -> str` = begin + `\n` + body + end + `\n`; body normalised to end with exactly
       one `\n` (empty body → no body line).
     - `upsert(text, body, style, position) -> str` (`text` `None`/`""` = no file; `position` `top`|`bottom`):
       no file → the block alone. Block present → that span replaced by `render_block` (canonical markers),
       everything else byte-identical. No block: `top` → block + `\n` + text; `bottom` → text +
       (`\n` if text does not end with `\n`) + `\n` + block.
     - `remove(text, style) -> str`: no block → unchanged. Else drop the span; then if the span started at offset 0
       and is followed by `\n`, drop that one `\n`; else if it is preceded by `\n\n`, drop one `\n`.
       Round trip: for every `T` that is empty or ends with `\n` and has no markers,
       `remove(upsert(T, b, s, p), s) == T` for both positions (property-tested). `T` without a final newline
       comes back with one (documented).
     - `body_sha256(text, style) -> str | None` = sha256 of the body (UTF-8); `None` if no block.
C43. **`gitignore.py`** — `exclude_path(root) -> Path` = `git rev-parse --git-path info/exclude` resolved against
     `root` (works in linked worktrees and sub-directories); plus `upsert`/`remove` thin wrappers fixing
     `style="hash"`, `position="bottom"`.
C44. **`json_keys.py`** — managed keys are dotted paths (`"permissions.deny"`); a key segment never contains a dot.
     - `merge(text, managed: dict) -> str`: `text` `None`/`""` → `{}`; must parse to a JSON object, else
       `KeysError` (comments/JSONC not supported). Sets each key, creating missing intermediate objects; an existing
       non-object intermediate → `KeysError`. Existing key order kept; new keys appended to their parent object.
       Output `json.dumps(obj, indent=<indent>, ensure_ascii=False) + "\n"` where `<indent>` is the original's
       (first indented line: N spaces → N, tab → `"\t"`), default 2. Values (incl. lists) are replaced whole.
     - `remove(text, keys) -> str`: deletes those keys (missing → ignored), then removes intermediate objects that
       became empty; same formatting rule.
     - `values_sha(text, keys) -> dict[str, str | None]` = sha256 of
       `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, `None` if absent.
     - Round trip: if `T == json.dumps(obj, indent=n, ensure_ascii=False) + "\n"` and none of the managed keys (nor
       their newly created parents) exist in `T`, then `remove(merge(T, m), m.keys()) == T`.
C45. **`toml_keys.py`** (tomlkit) — same API as C44 (`merge`, `remove`, `values_sha`; sha over the same canonical
     JSON of the plain value). Dotted key `a.b` = key `b` in table `a`. `merge(T, {}) == T` byte-identical;
     untouched parts keep comments, order and formatting; `remove(merge(T, m), m.keys()) == T` when the managed
     keys and their tables are absent from `T`. Parse error → `KeysError`.

### Engine additions and `init` (T4.5) — `engine.py`, `commands/init.py`, `main.py`

C46. **Ownership and bodies.**
     - Rendered files (everything Copier writes, except `.kuanflow/cache/**`): path matching a
       `_skip_if_exists` glob of that template's `copier.yml` (`fnmatch`-style, `**` = any depth) → `local-owned`;
       `.kuanflow/config.yaml` → `merge-required`; everything else (incl. `.copier-answers.yml`) →
       `template-managed`.
     - Blocks, project mode, `project` template only (bodies = `templates/project/blocks/*.jinja` rendered with
       `jinja2.Environment(undefined=StrictUndefined, keep_trailing_newline=True)` and the final answers incl.
       `kuanflow_version`):

       | target | body | style | position | when |
       |---|---|---|---|---|
       | `AGENTS.md` | `agents.md.jinja` | html | top | always |
       | `CLAUDE.md` | `claude.md.jinja` | html | top | always |
       | `.gitignore` | `gitignore.jinja` | hash | bottom | always |
       | `.github/pull_request_template.md` | `pr-template.md.jinja` | html | bottom | always |
       | `.worktreeinclude` | `worktreeinclude.jinja` | hash | bottom | `use_orca` true (review F8b) |

     - Personal mode (Q-16, PER-01..06): **no** block in any of those files. Instead one hash/bottom block in
       `exclude_path(root)` (manifest path `git:info/exclude`) whose body is `# Kuanflow (personal mode)` followed
       by one line per entry, sorted: `/<p>/` for the directories `.kuanflow` and `kuan-workbench`, and `/<p>` for
       every other file Kuanflow creates, where `<p>` is relative to the **git toplevel** (so `--root` sub-dirs
       work). Personal mode must not create or modify any path tracked by git: if a planned change touches a
       tracked path → `KuanflowError` before writing anything.
     - `engine.require_clean_worktree(root, *, allow_dirty=False)`: `git status --porcelain --untracked-files=all
       -- .` in `root` (ignored files do not count); non-empty and not allowed → `DirtyTreeError` listing the paths.
     - `engine.render_tree(data, *, template, version=None) -> dict[str, tuple[bytes, bool]]`: renders with
       `render()` into a temp dir (removed afterwards) and returns `{posix path: (bytes, executable)}` without
       `.kuanflow/cache/**`. Copier/Jinja errors (e.g. C26a validator) → `RenderError` with the message.
       `init` never runs Copier inside the project, so Copier's dirty-tree rule and `.kuanflow/cache/` ordering
       (ADR-0002) do not apply to `init`.

C47. **`kuanflow init [--here] [--agent A] [--personal] [--template project|knowledge-repo] [--yes] [--dry-run]
     [--root PATH] [--data-file FILE] [--force]`** (CMD-01..08, CMD-23..25). `--here` is accepted and is the
     default. Steps, in order; any error → exit 1 with **no file written**:
     1. Root (C37). `--agent` with a non-empty value → error `no agent adapters in this version: <A>` (P5).
        `--personal` with `--template knowledge-repo` → error.
     2. Existing manifest: different `kuanflow_version` (→ "run `kuanflow upgrade`"), `mode` or `template` → error.
     3. Unless `--dry-run`: project mode → `require_clean_worktree`; personal → dirty allowed. With `--dry-run`
        a dirty tree only prints a warning.
     4. `answers = collect_answers(…)`. Print every answer (`key: value`, sorted) and the detected agents
        (`Detected agents: claude, codex — adapters arrive in a later version` or `none`). Without `--yes` and
        without `--dry-run`: prompt `Apply? [y/N]`; anything but y/yes → exit 1, nothing written.
     5. Plan (C41), via `render_tree`:
        - `local-owned`: create if absent; if present → skip (`skip <path> (exists, project-owned)`), never read
          or changed.
        - `template-managed` / `merge-required`: absent → create (mode `0o755` if executable); same bytes → no-op
          (an exec-bit difference is a mode change); different → **update** if the manifest has an entry for the
          path whose sha256 equals the disk bytes (unchanged since Kuanflow wrote it), else it is a **conflict**.
        - Blocks (C46): upsert; if a block exists with a different body → update if the manifest's block sha256
          equals the current body sha256, else conflict. Broken markers → `BlockError`.
        - Conflicts without `--force` → error listing every conflicting path (`modified since install: <p>`), exit
          1. With `--force` they are overwritten (and backed up by `apply`).
        - The new manifest (C40) is part of the plan. Manifest `files` = every rendered file Kuanflow created now
          or that the previous manifest already listed (local-owned ones keep their recorded entry when skipped),
          plus every block. If the plan has no other change, the manifest is not rewritten (byte-identical; TST-11).
     6. `--dry-run`: print `diff_text(plan)` then a summary; exit 0; nothing is written (no backup dir, no cache,
        no exclude change).
     7. Apply (C41, backups on). Print one line per change: `create <path>`, `update <path>`, `delete <path>`,
        then `Kuanflow <version> installed (<mode> mode)` or `Nothing to change`. Then run the doctor (C49), print
        its report, and exit with the doctor's code.
     - `--template knowledge-repo`: no detection, no blocks; answers from existing answers file and `--data-file`.
     - Monorepo (`--root services/a` or cwd inside it): everything is relative to that root; clean-tree check is
       limited to it; detection reads only it.

### Status, doctor, uninstall, promote (T4.5, T4.6)

C48. **`kuanflow status [--root PATH]`** (CMD-18) — no manifest → `NotInstalledError` (exit 1). Prints:
     `Kuanflow <manifest version> (<mode> mode, template <template>)`, `CLI <cli version>`,
     `Agents: <a, b | none>`, then one line per problem in path order: `modified <path>` (template-managed /
     merge-required whose sha256 differs), `missing <path>` (any non-block entry whose file is absent, except
     local-owned), `block-edited <path>` (body sha differs), `block-missing <path>` (no block / file absent);
     broken markers → `block-broken <path>`. No problem → `All managed files match the manifest.` Exit 0.
C49. **Doctor** — `doctor.run(root, agents=()) -> list[Check]` (`Check(level, name, message)`, level
     `OK`|`WARN`|`FAIL`); `kuanflow doctor [--agent A] [--root PATH]` prints `"{level:<4} {name}: {message}"` per
     check, then `doctor: <n> ok, <n> warn, <n> fail`; exit 1 if any FAIL, else 0. `--agent` with a value → error
     (P5). Checks (names fixed), project template:
     - `manifest`: present and valid (absent/invalid → FAIL and the other checks are skipped).
     - `config`: `.kuanflow/config.yaml` parses and validates against the shipped schema (FAIL otherwise).
     - `commands`: for `build`, `test`, `verify`: first shell word resolvable — contains `/` → file relative to root
       exists and is executable; else `shutil.which` (through `doctor.shutil.which`). Unresolvable → WARN (never
       executed, never FAIL).
     - `scripts`: each `.kuanflow/scripts/*.sh` listed in the manifest exists, is executable and matches its sha256
       → else FAIL.
     - `python`: `python3 -c "import yaml"` succeeds → OK, else WARN (guards then allow everything).
     - `blocks`: each manifest block present with matching body → OK; edited → WARN; missing/broken → FAIL.
     - `version`: CLI version (`engine.current_version()`) < `kuanflow.min_version` (SemVer order) → FAIL; manifest
       `kuanflow_version` ≠ CLI version → WARN.
     - `answers`: `.copier-answers.yml` `_commit` == `v<manifest kuanflow_version>` → OK, else WARN.
     Knowledge-repo template: only `manifest`, `version`, `answers`.
C50. **`kuanflow uninstall [--dry-run] [--force] [--root PATH]`** (CMD-21, TST-15) — no manifest → exit 1. Project
     mode requires a clean tree (`DirtyTreeError`), personal does not. Per manifest entry:
     template-managed / merge-required → delete if its sha256 matches; if modified → `keep <path> (modified; use
     --force)` unless `--force`; local-owned → keep (never touched); managed-block → remove the block (C42); if
     `created` and the rest is `""` → delete the file; `git:info/exclude` → remove its block. Then delete
     `.kuanflow/manifest.json` and `.kuanflow/cache/`, and every directory left empty by these deletions (never
     the root). No backups (project mode: everything is in git). `--dry-run`: print the diff, change nothing.
     Lines: `delete <p>`, `remove-block <p>`, `keep <p> (…)`; final `Kuanflow removed` . Exit 0.
     **C50a (personal mode):** local-owned entries whose sha256 still matches are deleted too (they are untracked
     and were created by Kuanflow); modified ones are kept (`keep <p> (modified)`). So personal init → uninstall
     leaves `git status --porcelain` exactly as before init.
     Guarantee: on a fixture, init → commit → uninstall leaves every pre-existing file byte-identical (newline
     exception of C42) and `docs/`, `kuan-workbench/` intact.
C51. **`kuanflow promote <draft> [--dry-run] [--root PATH]`** (CMD-20, Q-18) — `<draft>` relative to cwd; must be an
     existing `.md` file inside root, else exit 1. Reads `paths.adr` / `paths.runbooks` from
     `.kuanflow/config.yaml` (missing config → exit 1).
     - Kind: frontmatter `kind` (`adr`|`runbook`|`postmortem`), else filename prefix `adr-`, `runbook-`,
       `postmortem`; `postmortem` → exit 1 `postmortems go to the knowledge repo by pull request`; none → exit 1.
     - Title: frontmatter `title`, else first `# ` heading, else file stem without the kind prefix.
       Slug: NFKD, `đ`/`Đ` → `d`, drop non-ASCII, lowercase, runs of `[^a-z0-9]` → `-`, strip `-`, cut to ≤ 60
       chars at a `-` boundary when possible, empty → `untitled`.
     - ADR: number = 1 + max `NNNN` of files `^\d{4}-.*\.md$` in `paths.adr` (none → `0001`; `0000-template.md`
       counts as 0). Target `<adr>/<NNNN>-<slug>.md`. Frontmatter (created if absent, existing key order kept,
       `yaml.safe_dump(sort_keys=False, allow_unicode=True)`): `id: "NNNN"`, `title`, `status: accepted`,
       `date: <clock date>`, `kind` removed. Body after the frontmatter byte-identical.
     - Runbook: target `<runbooks>/<slug>.md`; `kind` removed from frontmatter if present; with no frontmatter the
       file is copied byte-identically.
     - Target exists → exit 1 (never overwrite `docs/`). Else write target, delete the draft, remove its parent
       `drafts/` dir if now empty. Print `promoted <draft> -> <target>`. `--dry-run` prints the same line prefixed
       `would promote`, writes nothing.

### Fixtures and command wiring (T4.1c, T4.5)

C52. **Fixtures** — `cli/tests/fixtures/build.py`: `build(name, dest) -> Path` creates a git repo (`main` branch,
     isolated git env as C36d with a fixed identity and date) and commits all files once (except `empty`):
     - `empty`: `git init` only, no commit.
     - `maven`: `pom.xml`, executable `mvnw`, `src/main/java/com/example/App.java`,
       `src/main/resources/db/migration/V1__init.sql`, `CLAUDE.md` (two paragraphs of project notes),
       `.gitignore` (`target/`, `*.log`).
     - `gradle`: `build.gradle.kts`, `settings.gradle.kts`, executable `gradlew`, `.claude/settings.json`
       (`permissions.allow` and `permissions.deny` with project entries, indent 2).
     - `monorepo`: `README.md`, `services/order-svc/{pom.xml,mvnw}`, `services/web/package.json`
       (scripts `build`, `test`, `lint`) + `services/web/pnpm-lock.yaml`.
     - `speckit`: `.specify/memory/constitution.md`, `.specify/templates/spec-template.md`, `specs/001-login/spec.md`,
       `AGENTS.md` (project section), `package.json` (scripts `test`).
C53. **Wiring** — `main.py` registers `init`, `status`, `doctor`, `promote`, `uninstall` (no `upgrade`, `agent`,
     `self` yet). Each command lives in `commands/<name>.py` as `run(…) -> int` taking the CLI options as keyword
     arguments (names as the long options with `_`), returns the exit code, and raises nothing but
     `KuanflowError`; `main.py` maps the return/exception to the exit code (C36a/C36b). `kuanflow --version`
     unchanged.

### Coverage
C54. `make verify` runs pytest with `--cov=kuanflow_cli --cov-fail-under=80` (whole package, PKG/plan P4).

### Clarifications accepted after T4.1 (tests encode these literal readings)
- C38: `detect().answers` has exactly `project_name`, `stack`, `protected_paths`, `use_orca` + the stack's command
  keys; a *file* where a directory is expected does not count; non-object/non-UTF-8 `package.json` = invalid.
- C39: underscore keys and other templates' questions in a data file are unknown → `AnswersError`.
- C40: `Manifest(...)` defaults `manifest_version=1` and, when `source` is not given, computes it from
  `KUANFLOW_SOURCE` + `@v<kuanflow_version>`; a `source` read from a file is kept. `read()` accepts any field/file
  order, `dumps()` canonicalises. `diff` "changed" = same path, any field differs.
- C41: no `diff --git` line; a same-bytes change with a different mode is kept (old mode of an existing file read
  as shown in the tests); any `..` component is invalid; backup suffix `-<digits>`.
- C42: `upsert`/`remove` raise `BlockError` on broken markers; body normalisation strips all trailing newlines and
  adds one; indented markers are not recognised.
- C44/C45: objects that were already empty are not pruned; object values are replaced whole.
- C47: skipped pre-existing local-owned files are not in the manifest; manifest `agents` is `[]` in P4.

## Tasks

| ID | Role | Files | Deps | Status |
|---|---|---|---|---|
| T4.0 | Coordinator | this plan; `cli/src/kuanflow_cli/{errors,clock}.py` | P3 | [ ] |
| T4.1a | Test Eng A | `cli/tests/template/test_render_project.py` (C28c–C28e only), `cli/tests/test_root.py`, `cli/tests/test_detect.py`, `cli/tests/test_manifest.py` | T4.0 | [ ] |
| T4.1b | Test Eng B | `cli/tests/test_plan.py`, `cli/tests/patchers/test_{managed_block,gitignore_patcher,json_keys,toml_keys}.py` | T4.0 | [ ] |
| T4.1c | Test Eng C | `cli/tests/fixtures/build.py`, `cli/tests/commands/test_{cmd_init,cmd_dry_run,cmd_idempotent,cmd_personal,cmd_status,cmd_doctor,cmd_promote,cmd_uninstall,cmd_exit_codes,cmd_root}.py` | T4.0 | [ ] |
| T4.2 | CLI Eng 1 | `root.py`, `detect.py`, `manifest.py` | T4.1* | [ ] |
| T4.3 | CLI Eng 2 | `plan.py`, `patchers/{managed_block,gitignore,json_keys,toml_keys}.py` | T4.1* | [ ] |
| T4.4 | Template Eng | `templates/project/template/.kuanflow/config.yaml.jinja` (C28c–C28e) | T4.1a | [ ] |
| T4.5 | CLI Eng 3 | `engine.py` (C46 additions), `main.py`, `commands/{__init__,init,status,uninstall}.py` | T4.2, T4.3 | [ ] |
| T4.6 | CLI Eng 4 | `doctor.py`, `commands/{doctor,promote}.py` | T4.2, T4.3 | [ ] |
| T4.7 | Coordinator | `Makefile` (C54), CHANGELOG, VERSION `0.4.0-dev` | all | [ ] |

## Verify (phase exit)
`make verify` exit 0 incl. coverage ≥ 80 %; §12.5 tests green on the 5 fixtures (init, dry-run, idempotent,
personal, uninstall); RED of T4.1 recorded; adversarial review PASS.

## Evidence log

## Decisions log
- D-P4-1: `init` renders into a temp dir and applies a change plan to the project (no Copier run inside the
  project): one path for dry-run, backups, personal mode and idempotency. `.copier-answers.yml` still records
  `_src_path: .kuanflow/cache/template-repo`, so P6 `run_update` works after re-assembling the cache.
- D-P4-2: `init` refuses to overwrite a template-managed/merge-required file or block that differs from what the
  manifest recorded (or exists without a manifest entry) unless `--force` (OWN-06).
- D-P4-3: `uninstall` keeps user-modified Kuanflow files unless `--force` and makes no backups (project mode needs a
  clean tree, so git has everything).
- D-P4-4: personal mode writes no block into tracked files; it lists its files in `info/exclude` (Q-16). Agent-local
  files (`CLAUDE.local.md`, `settings.local.json`) come with the P5 adapters.
- D-P4-5: usage errors exit 1, not Click's 2 (2 is reserved for `upgrade --check`).

## Status (update before any context reset)
- T4.0 in progress.
