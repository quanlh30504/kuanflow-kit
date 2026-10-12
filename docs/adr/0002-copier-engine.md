# ADR-0002: Copier as the render/3-way-merge engine via a synthetic template repo

- **Status:** Accepted (Gate P1, 2026-10-12)
- **Date:** 2026-10-12
- **Spike:** S1 (resolves Q-09; informs Q-06, Q-10, Q-22)

## Context

Kuanflow's project template lives in the monorepo at `templates/project/` (`copier.yml` with
`_subdirectory: template`), and the guard scripts live only in `plugins/kuanflow/scripts/` (Q-10).
PKG §9.3/§9.5/§10.2 expect Copier, used as a Python library, to render Kuanflow-owned files on
`init` and to do a 3-way merge on `upgrade`. Copier's update has to rebuild the *old* render from a
git repo + ref, so the template must be a git repo whose versions are tags.

The Gate 0 design (Q-09 option A): for each run, the CLI **assembles a synthetic local git template
repo**. It copies `templates/project/*` and the scripts into a directory, then makes one commit and
one `v<ver>` tag per version, oldest first. After that it calls `copier.run_copy` / `copier.run_update`
against that repo. This spike checks whether that works with the current Copier and records what the
CLI has to add on top.

Setup: Copier **9.18.2** (latest available via uv on 2026-10-12), Python 3.13.5, git 2.43.0. The spike
used a minimal template shaped like PKG §6.3: `stack` choices, a Jinja-computed `build_cmd` default,
and `_skip_if_exists: [docs/adr/*.md, kuan-workbench/**]`. Its files were `.kuanflow/config.yaml.jinja`,
`.kuanflow/scripts/guard.sh`, `docs/adr/0000-template.md` and `kuan-workbench/work/.gitkeep`. The
destination was a git repo that already had committed files. The spike code was throwaway and is not
in the repo.

## Decision

**The design holds, with one required change.** The synthetic repo must be re-assembled at a
**stable path that is recorded in the answers file**. A fresh random temp dir does not work.

1. The CLI assembles the synthetic repo at **`.kuanflow/cache/template-repo`**, relative to the
   project root. `.kuanflow/cache/` must be git-ignored. The CLI calls Copier with
   `cwd = project root` and `src_path=".kuanflow/cache/template-repo"`. Copier then stores
   `_src_path: .kuanflow/cache/template-repo`, which is relative, portable across machines and
   committed in `.copier-answers.yml`.
   - Accepted fallback: `~/.cache/kuanflow/template-repo`. Copier keeps the `~` as written, and it
     was verified to work. It is not preferred, because all projects on a machine would share one
     cache path.
2. On `upgrade`, the CLI wipes that directory and re-assembles it with **both** the installed
   version (read from the manifest or from `_commit`) and the target version, as successive
   commits and tags. Commit dates are fixed, so the SHAs are reproducible.
3. Calls:
   - `run_copy(src, dst, data=answers, defaults=True, vcs_ref="v<ver>", quiet=True)`
   - `run_update(dst, vcs_ref="v<target>", defaults=True, overwrite=True, conflict="inline", quiet=True)`

   `unsafe` stays at `False`, and the template must not use `_tasks`, `_migrations` or
   `_jinja_extensions`.
4. Migrations run only in the CLI framework. The `_migrations` block in PKG §6.3 is dropped (Q-09).
5. Option B (Copier reads `templates/project` straight from the monorepo) is **rejected**; see (g).

## Evidence

Each item lists the call, then trimmed output.

**API (Copier 9.18.2).**
- `run_copy(src_path, dst_path='.', data=None, *, answers_file, vcs_ref, settings, exclude, use_prereleases, skip_if_exists, cleanup_on_error=True, defaults=False, user_defaults, overwrite=False, pretend=False, quiet=False, unsafe=False, skip_tasks=False, ask=()) -> Worker`
- `run_update(dst_path='.', data=None, *, …same…, conflict: 'inline'|'rej'='inline', context_lines=3, unsafe=False, skip_answered=False, skip_tasks=False, ask=()) -> Worker`
- **`run_update` has no `src_path` parameter.** It always reads the template location from
  `_src_path` in the answers file. Importing `copier.Worker` raises a DeprecationWarning
  ("intended for internal use only"), so the CLI must use only `run_*`.

**(a) Copy into an existing repo**: works. Unrelated files are untouched.
```
run_copy(tplA, proj, data={project_name: order-svc, stack: node}, defaults=True, vcs_ref="v0.1.0")
status: ?? .copier-answers.yml  ?? .kuanflow/  ?? docs/adr/0000-template.md  ?? kuan-workbench/
pre-existing files unchanged: True        # `git ls-files -s` identical; docs/adr/0001-existing.md intact
config.yaml: build_cmd: "npm run build"   # Jinja default resolved from stack
answers: _commit: v0.1.0 / _src_path: <abs path> / build_cmd: npm run build / project_name / stack
```
Copier writes the answers file only when the template contains
`template/{{ _copier_conf.answers_file }}.jinja` (`{{ _copier_answers|to_nice_yaml }}`). Without it:
`answers file written? False`. Computed defaults such as `build_cmd` are saved as answers, so a
later change to the default formula does **not** reach projects that are already installed.

**(b) 3-way update**: works. The local customisation is kept and the upstream changes are applied.
Locally, `timeout: 30→99` was changed and a project ADR was added. Upstream v0.2.0 changed
`retries: 1→3` and `guard.sh`.
```
run_update(proj, vcs_ref="v0.2.0", defaults=True, overwrite=True)
 M .copier-answers.yml   (-_commit: v0.1.0 +_commit: v0.2.0)
 M .kuanflow/config.yaml (timeout: 99 kept; -retries: 1 +retries: 3)
 M .kuanflow/scripts/guard.sh (-echo guard v1 +echo guard v2)
```

**(c) Conflict**: Copier **returns normally and raises no exception**. The `Worker` it returns has
no conflict flag. The markers are written inline, and the conflict is **recorded in the git index**.
```
<<<<<<< before updating
timeout: 99
log_level: debug
=======
timeout: 30
log_level: warn
>>>>>>> after updating
git status: UU .kuanflow/config.yaml
git diff --name-only --diff-filter=U  ->  .kuanflow/config.yaml
git ls-files -u  ->  stages 1/2/3 present
```
- `conflict="rej"` is unsafe for us. The file is overwritten with upstream content
  (`timeout: 30`, `log_level: warn`), and the local edits survive only in `config.yaml.rej`.
  It also leaves no unmerged index entry.
- Edits on **adjacent lines** conflict even when the local and upstream changes touch different
  keys. `context_lines=1` does not change that. Separating the keys with a blank line removes the
  conflict:
  ```
  separator='\n'   conflicted=True
  separator='\n\n' conflicted=False  ['timeout: 99', 'log_level: warn', …]
  ```

**(d) Dirty destination**: refused. An **untracked** file counts as dirty too. The check is
`git status --porcelain <dst>`, so files that are git-ignored do not count.
```
untracked scratch.txt -> UserMessageError | Destination repository is dirty; cannot continue. Please commit or stash your local changes and retry.
modified README.md    -> UserMessageError | (same message)
```

**(e) `_skip_if_exists` on update**
```
deleted kuan-workbench/work/.gitkeep recreated? True
modified docs/adr/0000-template.md: "# locally edited template ADR"   (left alone)
project ADR 0002 kept? True
```
"Skip if exists" means exactly that: a file the user deletes is **re-created** on every update.

**(f) Answers file and ephemeral source**: works only when the source path is stable.
`.copier-answers.yml` stores `_commit` (the output of `git describe --tags --always`, so
`v0.1.0` when HEAD is on the tag) and `_src_path`, written exactly as passed. Update builds the old
render from `_src_path` at `_commit`, and the new render from `_src_path` at `vcs_ref`.
```
synthetic repo deleted, re-assembled at a different temp path:
  run_update -> ValueError: Local template must be a directory.
_src_path=".kuanflow/cache/template-repo" (cwd=project, dir git-ignored), wiped + re-assembled [v0.1.0, v0.2.0]:
  run_update -> OK (result identical to b)
_src_path="~/.cache/kuanflow/template-repo" -> stored literally with "~"; update OK
```
The answers file cannot be patched before an update, because any edit makes the tree dirty (d).
That is why the source path itself has to stay stable.

**(g) Template in a monorepo subdirectory**: **No.**
```
run_copy("<mono>/templates/project", vcs_ref="v0.1.0") -> OK, but answers have NO _commit (treated as plain dir; vcs_ref ignored)
run_update -> UserMessageError | Cannot update because cannot obtain old template references
"git+file://<mono>/templates/project", "<mono>/templates/project.git" -> ProcessExecutionError (git clone exit 128)
```
Copier only reads a local path as a git template when the path is the repo root (`is_git_repo_root`).

**(h) Downgrade**: not supported.
```
run_update(vcs_ref="v0.1.0") at v0.2.0 -> UserMessageError | You are downgrading from 0.2.0 to 0.1.0. Downgrades are not supported.
```

**(i) Dry run**: `pretend=True` writes nothing (`git status` empty, HEAD and `_commit` unchanged).
It produces **no diff**. With `run_copy` and `quiet=False` it prints only `create <path>` lines.
What worked instead was running the update for real in a throwaway clone, then diffing:
```
git clone -q <proj> <tmp>/dry && run_update(<tmp>/dry, vcs_ref="v0.2.0", ...) && git -C <tmp>/dry diff --stat
 .copier-answers.yml | 2 +-   .kuanflow/config.yaml | 2 +-
real project untouched: ''
```
Note: a throwaway clone does not contain git-ignored `.kuanflow/cache/`. For a dry run, the CLI
assembles the synthetic repo inside the clone.

**(j) Trust model**: with no `_tasks`, `_migrations` or `_jinja_extensions`, `unsafe=False` works.
Each of those features alone triggers:
```
UnsafeTemplateError | Template uses potentially unsafe feature: tasks.            (also: jinja_extensions)
```
`unsafe` is checked in both copy and update.

## Consequences

The CLI must implement these itself:
- **Synthetic repo builder** (`engine.assemble(versions)`):
  - copy `templates/project/**`, then copy `plugins/kuanflow/scripts/*` into
    `template/.kuanflow/scripts/` (Q-10);
  - add one commit per version with fixed author and committer dates, tagged `v<semver>`;
  - tag HEAD exactly, because `_commit` comes from `git describe`, and use tags that PEP 440 can
    parse, because Copier compares versions to block downgrades;
  - fetch old-version content per Q-06 (`.kuanflow/cache/sources/<ver>/`).
- **Ignore rule first:** `.kuanflow/cache/` must be git-ignored before Copier runs. Otherwise the
  cache itself makes the tree dirty (d). The gitignore patcher has to run, or already be committed,
  before `init` writes the cache. Personal mode uses `.git/info/exclude`.
- **Own clean-tree check** (PKG §10.2), run before Copier, with a clear message and an exit code.
  Copier only raises a generic `UserMessageError`, so the CLI should also catch `UserMessageError`
  and `UnsafeTemplateError` and map them to CLI errors.
- **Conflict detection:** after `run_update`, run `git ls-files -u` (or
  `git diff --name-only --diff-filter=U`) limited to Copier-managed paths. As a backup, scan for
  `^<<<<<<< before updating`. Any hit means exit code 3 (PKG §9.5). Always use `conflict="inline"`.
- **Dry-run diff:**
  - `upgrade --dry-run`: clone the project into a temp dir, assemble the synthetic repo inside it,
    run the real update, then show `git diff`;
  - `init --dry-run`: render into an empty temp dir, then diff against the project.
- **Rollback and downgrade** (PKG §10.5): Copier cannot do it. The CLI uses git
  (`git revert` / checkout of the pre-upgrade commit) or its backups.
- **Template authoring rules:**
  - ship `template/{{ _copier_conf.answers_file }}.jinja`;
  - in `config.yaml.jinja`, separate the user-editable keys with a blank line or comment so that
    neighbouring edits do not conflict;
  - do not use `_tasks`, `_migrations` or `_jinja_extensions`;
  - remove `_migrations` and `{{ _copier_conf.src_path }}` from PKG §6.3.
- **`_skip_if_exists` re-creates deleted files.** That is acceptable for `kuan-workbench/**`
  skeleton files. For `docs/adr/0000-template.md`, either accept it or have the CLI pass
  `exclude=[…]` on update for skeleton files that are seed-only. TODO(verify) below.
- **Computed defaults are frozen in the answers.** A change to a default's formula
  (e.g. `build_cmd`) only reaches existing projects through a CLI migration or through
  `data=` on update.
- `.copier-answers.yml` remains Copier's state, and the manifest (Q-22) records the Kuanflow
  version. The two must agree: `_commit == "v" + manifest.kuanflow_version`. `doctor` should check
  this.
- Adapter files (`.claude/skills/**` etc.) are not rendered by Copier. Their 3-way merge is done
  by the CLI with `git merge-file`, as Q-09 says. This spike did not test that.

## Pinned version

- `pyproject.toml`: `copier>=9.18.2,<10`.
- Tested exactly: `copier==9.18.2` (Python 3.13.5, git 2.43.0).
- Set `_min_copier_version: "9.18.2"` in `copier.yml`.
- Keep a CLI integration test that repeats (b), (c) and (f) on every Copier bump. The relative
  `_src_path` behaviour is observed behaviour, not a documented contract.

## Open items

- TODO(verify): relative `_src_path` when the CLI is run from a sub-directory. The CLI must
  `chdir` to the project root (`find_root`) before calling Copier. Add a test.
- TODO(verify): Windows path handling of `.kuanflow/cache/template-repo` and `~` (out of scope
  for v0.1 if Linux/macOS only).
- TODO(verify): behaviour when a template file is **deleted** upstream between versions. Expected:
  Copier deletes it if the user has not modified it. Not exercised in this spike.
- TODO(verify): whether `exclude=` on update stops the re-creation of a deleted
  `docs/adr/0000-template.md` without breaking the initial copy.
