---
name: knowledge-gardening
description: Use for the weekly knowledge check, or when asked which generated wiki pages are out of date. Finds wiki pages whose source code changed since their source_commit, marks them stale and proposes updates as a pull request. Never merges.
---
# Knowledge gardening

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Required keys: `paths.wiki`. Optional: `knowledge.repo`. If a required key is missing, stop and ask the human.
3. Work on a branch, never on main. If the working tree has uncommitted changes, stop and ask.

## Steps
1. List the pages under `<paths.wiki>` whose frontmatter has `generated: true`.
2. For each page, read `source_commit` and `source_paths`, then list what changed since:
   `git diff --name-only <source_commit> HEAD -- <source_paths>`.
   - Files changed → the page is stale.
   - `source_commit` missing or unknown to git → stale ("cannot verify").
   - Nothing changed → fresh; leave the page untouched.
3. For each stale page: set `stale: true` in the frontmatter, then re-check every claim against the current
   code (`file:line`), update the text, set `source_commit` to HEAD and `stale: false`, and clear `reviewed_by`.
4. Never touch human-approved docs (`<paths.adr>`, `<paths.runbooks>`); if they look outdated, list them for
   the human instead.
5. Commit on the branch and open a pull request (or prepare it for the human). Never merge it.

## Output
A list of stale pages with the changed files that made them stale, and one PR proposing the updates.
If nothing is stale, say so and change nothing.

## Never
- Treat the wiki as truth: code always wins over the wiki.
- Merge your own PR.
