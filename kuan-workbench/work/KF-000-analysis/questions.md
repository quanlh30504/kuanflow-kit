---
work: KF-000-analysis
status: answered (Gate 0 approved 2026-10-12 — all recommendations accepted)
date: 2026-10-12
---
# Questions — Kuanflow build, Phase 0

## Summary
The two docs are consistent on architecture (solution B: CLI + Copier engine + shared content + adapters) and on
the five ownership classes. Gaps are mostly (a) mechanics the docs mark "verify against current version",
(b) a few places where examples in different sections disagree, and (c) content that is described but not written
(7 of 10 skills, 6 of 9 agents, 11 of 12 commands).

Legend: **[BLOCKING]** = need your answer before Gate 1 plan can be final.
**[DEFAULT]** = I will apply the recommendation unless you object.
Each question: context → options → recommendation.

---

## A. Blocking questions

### Q-01 [BLOCKING] Doc file names
Brief cites `docs/packaging.md` / `docs/playbook.md`; repo has `docs/ai-workflow-packaging-guide.md` /
`docs/ai-sdlc-workflow-playbook.md`. PKG §4 says the target names are `packaging.md` / `playbook.md`.
- A. `git mv` to the §4 names in P1 (content unchanged byte-for-byte; a rename is not an edit).
- B. Keep current names; README links to them.
- **Recommend A** — matches §4 layout, and the docs' own last line says it lives at `docs/packaging.md`.

### Q-03 / Q-23 [BLOCKING] Versioning, tags, branches, upgrade-test baseline
- The brief tags each phase `v0.<phase>.0-dev`. Templates only exist from P3 and `init` from P4, so the P6 exit
  criterion "tag v0.1.0 → upgrade to HEAD" has nothing to upgrade from.
- `plugin.json` needs SemVer (`0.1.0-dev`), Python needs PEP 440 (`0.1.0.dev0`).
- Options for the upgrade test baseline:
  - A. Test builds its own throw-away git repo of the Kuanflow source (commit "old" = a frozen copy of
    templates/content, commit "new" = working tree), tags both, uses it via `file://`. Independent of real tags.
  - B. Use real tag `v0.4.0-dev` (first tag where `init` works) as baseline.
- Branching: work on `main` directly, or on a long-lived `build/v0` branch with per-task branches merged into it?
- **Recommend:** VERSION holds SemVer (`0.1.0-dev` → bumped per phase); `check_versions.py` normalises SemVer↔PEP 440;
  upgrade test uses **A** (deterministic, no network) **plus** one test against the real previous phase tag once it
  exists; work on per-task branches/worktrees merged into `main` with tags at phase end, no push unless you ask.

### Q-04 [BLOCKING] W4/W5/W6/W10 depend on external Superpowers skills
PB §5 maps W4→`writing-plans`, W5→`executing-plans`+`test-driven-development`, W7→`systematic-debugging`,
W10→`writing-skills`. These are Tier-1 community skills (PB §8.1) and are **not** in the Kuanflow skill list (PKG §4).
The brief says "skills W0–W10 + …", which could be read as one skill per workflow.
- A. Ship exactly the 10 skills of PKG §4. Commands `w4-plan`, `w5-implement`, `w6-test`, `w10-capture` are
  self-contained (plan template from PB §13.3, rules from PB W4–W6, W10 table) and say "if the Superpowers skill X is
  installed, follow it as well". No hard dependency.
- B. Add new skills (`write-plan`, `implement-phase`, …) — features beyond the docs.
- C. Vendor/mirror Superpowers (PKG §15 allows fork + pin) and depend on it.
- **Recommend A.**

### Q-06 [BLOCKING] Where `pyproject.toml` lives and how the CLI gets its content
PKG §9.2 install command `uvx --from git+…/kuanflow.git@vX kuanflow` requires a `pyproject.toml` at repo root, but
PKG §4/§18.2 put it in `cli/`. Also a wheel built from `cli/` would not include `plugins/` and `templates/`.
For upgrades the CLI also needs the **old** version's content (3-way merge base).
- A. Keep `cli/pyproject.toml`; bundle `plugins/kuanflow` + `templates/` into the wheel at build time
  (hatch `force-include`); install URL becomes `git+…@vX#subdirectory=cli`; old-version content is fetched from
  `manifest.source` at the old tag into `.kuanflow/cache/sources/<ver>/` (git, `file://` in tests).
- B. Move `pyproject.toml` to repo root (package code stays in `cli/src`), so the doc's command works verbatim;
  same bundling/fetch for content.
- **Recommend A** (keeps §4 layout); README documents `#subdirectory=cli`. Either way: verify in a P1 spike, ADR-0001.

### Q-08 [BLOCKING] Git hooks: what they check and how they are installed
PKG §9.6.3: init always installs pre-commit/pre-push hooks calling the same scripts. PKG §9.8: project mode installs
"via the repo's hook manager", personal mode into `.git/hooks`. Neither the checks nor the manager is specified.
- Checks proposal: **pre-commit** — for each staged *modified/deleted* (not added) file, run
  `guard-protected-paths.sh` with `{"tool_input":{"file_path":…}}`; **pre-push** — block pushes whose remote ref is
  main/master (read refs from stdin) by feeding a synthesised `git push … <ref>` to `guard-bash.sh`.
- Install options: A. Always write `.git/hooks/{pre-commit,pre-push}` (managed block inside the hook file, chain any
  existing hook); if husky/lefthook/pre-commit/`core.hooksPath` is detected, do not touch it and print the snippet +
  doctor warning. B. Commit hooks under `.kuanflow/githooks/` and set `core.hooksPath` (collides with existing managers).
- **Recommend proposal checks + A** for both modes in v0.1.

### Q-09 [BLOCKING-tech, decided by spike] Copier with a template in a monorepo subdirectory
Copier's versioned `update` reconstructs the old render from a git **repo** + ref; our template is
`templates/project/` inside the monorepo, and scripts come from `plugins/kuanflow/scripts/`.
- A. CLI assembles a **synthetic local template repo** per version (copy `templates/project/` + scripts → temp git
  repo, commit, tag `v<ver>`), then calls `run_copy`/`run_update` against it. Old version = assembled from fetched
  old source. Answers file stores the version.
- B. Point Copier at the monorepo root with `_subdirectory` — would require `copier.yml` at repo root (breaks §4).
- Also: adapter files (`.claude/skills/**`, …) are template-managed but **not** Copier-rendered, so their 3-way merge
  must be done by the CLI (`git merge-file` with base = old version content). Copier `_migrations` (PKG §6.3) vs
  `cli/…/migrations/` (PKG §4): use only the CLI framework.
- **Recommend A + CLI merge-file for adapter files + CLI-only migrations.** Validate in P1 spike; record ADR-0002.

### Q-16 [BLOCKING] Claude command naming, AGENTS.md block text, personal-mode files
1. `/kuanflow:w8-verify` (PKG §6.5 block, §5.1) is the **plugin** namespace. CLI-installed `.claude/commands/` (or
   skills) likely appear as `/w8-verify` (to verify on Claude Code 2.1.296). AGENTS.md is also read by Codex.
   - A. Keep doc text verbatim (works only with plugin channel). B. Install commands under a `kuanflow` subfolder and
     use whatever name Claude shows, adjust block text to "run `/kuanflow:w8-verify` (plugin) or the
     `verify-agent-output` skill". C. Agent-neutral wording: "run the verify-agent-output skill (W8)".
   - **Recommend:** verify actual naming in P5; block text = doc text with one agent-neutral addition (C-style).
     This deviates from PKG §6.5 wording → needs your OK.
2. Personal mode must keep `git status` clean, so it may not modify **tracked** files. Proposal: Claude →
   `.claude/settings.local.json` + `CLAUDE.local.md` (`@AGENTS.md`-equivalent pointer to `.kuanflow/`); Codex hooks/
   instructions only if the target file is untracked, else skip with doctor warning; everything created goes into
   `.git/info/exclude`. **Recommend this.**

### Q-19 [BLOCKING-scope] OpenCode and Kiro in v0.1?
Brief P5 includes them; docs mark them Tier 2 and "formats change fast".
- A. All four in P5. B. claude + codex + githooks in v0.1; opencode + kiro as P5b after Gate 5 (same phase, separate
  review). C. Defer to after v0.1.
- **Recommend B.**

### Q-24 [BLOCKING-env] `bats` is not installed
Verify suite needs `bats tests/bats`. Options: A. you run `! sudo apt-get install -y bats`; B. vendor bats-core as a
pinned git submodule under `tests/bats/lib/` (no network at test time); C. `npx bats@<pinned>`.
- **Recommend A** for local + apt in CI (as PKG §18.6). B as fallback if no sudo.

---

## B. Default decisions (apply recommendation unless you object)

### Q-02 Python version — PKG §18.2 says `>=3.10`; known decision ≥ 3.11 wins. Record in ADR-0001.

### Q-05 Subagents and tool allowlist
- Ship the 9 agents of PKG §4. `rca-data-state` and a consolidator (PB §6.2/§6.4) → later (need DB/replica access;
  consolidation is done by the debug-incident skill itself, PB §8.6 step 4).
- Agents without full text (locator, pattern-finder, 4× rca-*) are written from PB W3 / §6.4 scope table only.
- Allowlist: `Read, Grep, Glob, Bash, Write, Edit, WebFetch, WebSearch`. Read-only roles (locator, analyzer,
  pattern-finder, rca-*, adversarial-reviewer) must not have `Write`/`Edit`; check enforced in `check_skills.py`.

### Q-07 debug-incident collector
No infra is specified. Ship `schemas/context.schema.json` (from PB §6.5) and `scripts/collect_context.sh` that builds
`context.json` from **local inputs** (log/trace files + args), applies masking (`account_no`, `id_number`, phone,
email patterns), enforces the ≤ 50 KB budget, writes only to `.kuanflow/scratch/<work-id>/`, no network. Org-specific
sources are plugged in by extending the script (documented), not via `TODO`.

### Q-10 Guard scripts single source
Scripts live only in `plugins/kuanflow/scripts/`; the template does not keep copies — the synthetic template repo
(Q-09) pulls them in at render time. CI check: installed `.kuanflow/scripts/*` == plugin scripts byte-for-byte.

### Q-11 Config schema additions (all optional, with defaults — MINOR-compatible)
Add `guard.extra_block_patterns` (used by PKG §18.4), Copier questions `lint_cmd` and `ticket_pattern` (init asks for
"ticket pattern?" in PKG §9.7 but copier.yml has no question). `kuanflow_version` answer default comes from `VERSION`,
not the hard-coded `"1.4.0"`.

### Q-12 Config layers
v0.1 implements project + local (PKG §18.3 script). Defaults layer (`plugins/kuanflow/defaults/config.yaml`) and org
layer (`~/.config/kuanflow/org.yaml`) → later. User-level `~/.kuanflow/` is used only by W0/W9 output.

### Q-13 Ownership of `orca.yaml`, `.worktreeinclude`, `kuanflow-update.yml`
- `orca.yaml`: created only if absent (local-owned after creation), because projects already own it (detector uses it).
- `.worktreeinclude`: managed-block (`# kuanflow:begin` / `# kuanflow:end`).
- `.github/workflows/kuanflow-update.yml`: later (not in §6.1 tree; GitHub/GitLab choice open).
This deviates from PKG §6.4 diagram (orca.yaml template-managed).

### Q-14 PR template
Managed block (HTML comment markers) in `.github/pull_request_template.md` when the repo is GitHub or has no CI
marker; GitLab path (`.gitlab/merge_request_templates/`) → later.

### Q-15 Flags not in the §9.2 table
`--data-file`, `--root`, `--force`, `--keep-local`, `--yes` (upgrade): implement (documented elsewhere in PKG).
`--promote-to-project`: later. `self upgrade`: thin wrapper that runs
`uv tool install --force kuanflow-cli --from <source>@<latest tag>#subdirectory=cli`; `--dry-run` prints it.

### Q-17 Doctor scope
Checks: config parses + validates schema; required `commands.*` present and first token resolvable (not executed);
scripts present + executable + identical to manifest hash; python3 + PyYAML available; per agent: skills present where
that agent reads them, hooks registered (claude settings keys / codex hooks.json + feature flag), Tier-2 notice;
git hooks installed; CLI version ≥ `kuanflow.min_version`; managed blocks intact. Exit 0 green / 1 any error.
Org model-policy warning (PKG §15) → later (no policy format defined). `/kuanflow:doctor` command = run
`kuanflow doctor` if on PATH, otherwise perform the same checks manually and report.

### Q-18 `promote <draft>` type detection
Frontmatter `kind: adr|runbook`, else filename prefix `adr-` / `runbook-`, else error (exit 1). ADR: next 4-digit
number in `paths.adr`, slug from `title`, set `status: accepted`, `date`. Runbook: `paths.runbooks/<slug>.md`.
Postmortems are not promoted (they go to the knowledge repo by PR, PKG §6.2 diagram) → exit 1 with message.
Target exists → exit 1 (never overwrite `docs/`).

### Q-20 Detector fallbacks
Maven without `mvnw` → `mvn -q …`; Gradle without `gradlew` → `gradle …`. Node: package manager from lockfile
(npm/pnpm/yarn); build = `<pm> run build` if script exists; test = `<pm> test`; verify = `<pm> run verify` if exists
else test; python stack (pyproject) detection → later.

### Q-21 Knowledge-repo template scope for v0.1
Skeleton (`postmortems/`, `runbooks-shared/`, `taxonomy.md` from PB §7.5, postmortem + ADR templates), frontmatter
CI check script, `stale-wiki-check.sh <repo-path>` (compares `source_commit` vs HEAD on `source_paths` for
`kuan-workbench/wiki/*.md`). `build-index.py` = level-1 index (frontmatter → JSON). Search MCP → later.

### Q-22 Manifest details
Add `manifest_version: 1`. `installed_at` set on first install, preserved on re-init (idempotency); add `updated_at`
only when something changed. Managed-block `sha256` = hash of block **content**; managed-keys store
`{key: sha256(value)}` to detect hand edits.

### Q-25 CI/static details
- markdownlint: lint `plugins/`, `templates/`, `README.md` only (not the Vietnamese source docs).
- gitleaks in CI only.
- "No hard-coded build commands" also applies to `commands/` and `agents/`; exemption only inside fenced blocks
  marked `<!-- kuanflow:example -->`… (PKG §12.1 "trừ file ví dụ").
- Banned prompt patterns (PKG §15): "ignore previous instructions", disabling TLS (`-k`, `verify=False`,
  `NODE_TLS_REJECT_UNAUTHORIZED=0`), curl/wget to non-placeholder hosts.
- Runtime messages in English (load-config warning text in PKG §18.3 is Vietnamese).
- CI on GitHub Actions (origin is GitHub). `bats tests/bats`; eval runner `evals/run.sh` (+ `run_all.sh` wrapper with
  thresholds as in PKG §18.6).

---

## MVP cut proposal (v0.1 = must work end-to-end)

**In v0.1:** monorepo skeleton + tooling; 10 skills, 9 agents, 12 commands, 3 guard scripts + bats; project template
(java-maven, java-gradle, node, python, other) + config JSON Schema v1; knowledge-repo skeleton; CLI `init`, `status`,
`doctor`, `promote`, `uninstall`, `upgrade` (`--to/--check/--dry-run/--force/--keep-local/--yes`), `self upgrade`,
`agent add/remove`; patchers (managed block, JSON keys, TOML keys, gitignore); adapters **claude, codex, githooks**;
personal mode; manifest; backups; migrations framework (+1 test migration); plugin channel files; eval harness with
deterministic assertions + ≥ 1 behavior and 1 trigger case (LLM runs gated by `EVAL_API_KEY`); CI + release workflows;
README + onboarding; E2E smoke.

**Later:** opencode + kiro adapters (or P5b, Q-19); defaults/org config layers; `--promote-to-project`;
`kuanflow-update.yml` bot; `kuanflow-experimental` + beta marketplace; `.mcp.json` knowledge search; single-file
executables; org model-policy warnings; rca-data-state + consolidator agents; remaining 5 behavior eval cases;
GitLab variants; markdownlint of all docs; config schema N-1 compatibility (needs a v2).

## Answers (Gate 0, 2026-10-12)

Human decision: **"apply all recommendations"**; bats installed by the human.

| Q | Decision |
|---|---|
| Q-01 | `git mv` docs to `docs/packaging.md` / `docs/playbook.md` in P1, content byte-identical |
| Q-02 | Python ≥ 3.11 (ADR-0001) |
| Q-03/Q-23 | VERSION = SemVer (`0.1.0-dev`, bumped per phase); `check_versions.py` normalises SemVer↔PEP 440; upgrade test uses a synthetic `file://` source repo with two versions + one test against the previous real phase tag; per-task branches/worktrees merged into `main`, tag `v0.<phase>.0-dev` at phase end, no push unless asked |
| Q-04 | Exactly the 10 PKG §4 skills; w4/w5/w6/w10 commands self-contained, use Superpowers only if installed |
| Q-05 | 9 agents; allowlist `Read, Grep, Glob, Bash, Write, Edit, WebFetch, WebSearch`; read-only roles have no Write/Edit (static check) |
| Q-06 | `cli/pyproject.toml`; content bundled into wheel; install URL `…@vX#subdirectory=cli`; old content fetched from `manifest.source` into `.kuanflow/cache/sources/<ver>/` (verify in P1 spike, ADR-0001) |
| Q-07 | Local-input collector + schema + masking + 50 KB budget, writes only to scratch, no network |
| Q-08 | pre-commit = protected paths on staged modified/deleted files; pre-push = block main/master; install in `.git/hooks` with managed block + chaining; detected hook managers untouched → snippet + doctor warning |
| Q-09 | Synthetic local template repo per version for Copier; CLI `git merge-file` for adapter files; CLI-only migrations (spike in P1, ADR-0002) |
| Q-10 | Scripts single-sourced in `plugins/kuanflow/scripts/`; byte-equality check |
| Q-11 | Add `guard.extra_block_patterns`, questions `lint_cmd`, `ticket_pattern`; `kuanflow_version` default from VERSION |
| Q-12 | Layers project + local in v0.1; defaults/org later |
| Q-13 | `orca.yaml` create-if-absent; `.worktreeinclude` managed block; `kuanflow-update.yml` later |
| Q-14 | PR template managed block in `.github/pull_request_template.md`; GitLab later |
| Q-15 | Implement `--data-file`, `--root`, `--force`, `--keep-local`, upgrade `--yes`; `--promote-to-project` later; `self upgrade` wraps `uv tool install --force` |
| Q-16 | Verify Claude command naming in P5; AGENTS block = PKG §6.5 text + one agent-neutral addition (approved deviation); personal mode never touches tracked files (`settings.local.json`, `CLAUDE.local.md`, `.git/info/exclude`) |
| Q-17 | Doctor scope as proposed; policy warning later; `/kuanflow:doctor` runs CLI or manual checks |
| Q-18 | `kind:` frontmatter → filename prefix → error; ADR numbering; never overwrite docs/; postmortem not promotable |
| Q-19 | v0.1 adapters: claude, codex, githooks; opencode + kiro as P5b with separate review |
| Q-20 | Detector fallbacks as proposed |
| Q-21 | Knowledge-repo skeleton + frontmatter check + stale-wiki-check + level-1 index |
| Q-22 | `manifest_version: 1`; `installed_at` preserved; `updated_at` on change; block/key content hashes |
| Q-24 | Resolved: `bats` 1.10.0 at `/usr/bin/bats` (installed by human) |
| Q-25 | CI/static details as proposed (GitHub Actions, `bats tests/bats`, `evals/run.sh` + `run_all.sh`) |
