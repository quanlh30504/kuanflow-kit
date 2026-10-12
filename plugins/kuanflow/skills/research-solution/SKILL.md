---
name: research-solution
description: Use when you need to understand how existing code works today, or to compare 2–3 solution options for an approved spec. Produces research.md (facts with file:line, no proposals) and options.md (trade-offs), and an ADR draft when the choice is architectural.
---
# Research solution (W3)

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Resolve the work item, in this order: env `KUANFLOW_WORK` (a path or ticket key) → the ticket key in the
   branch name, matched with `work.ticket_pattern` → the `work` field of `.kuanflow/state.json` → ask the human.
   The work folder is `<paths.work>/<TICKET>-<slug>/`.
3. Required keys: `paths.work`, `paths.wiki`, `paths.adr`. Optional: `paths.runbooks`, `knowledge.repo`.
   If a required key is missing, stop and ask the human.

## Part 1 — research.md (facts only)
1. From `spec.md`, write neutral research questions: what exists, where, how it behaves. Do not reveal the
   intended change or a preferred solution in the questions.
2. Answer them in a context that sees only the questions, not the ticket or the spec. If you cannot open a new
   context, do not re-read the ticket or the spec while researching.
3. Split the work, so results come back compressed:
   - codebase-locator: where the relevant code lives.
   - codebase-analyzer: how the current flow works.
   - pattern-finder: which patterns are in use and which are deprecated.
   - Knowledge lookup: generated wiki pages under `<paths.wiki>` (they tell you where to look; always confirm
     against current code), accepted ADRs under `<paths.adr>`, runbooks under `<paths.runbooks>`, and
     postmortems in the knowledge repo (`knowledge.repo`).
   - Library and framework docs (web search, if allowed): check the version the project actually declares.
   - If subagents are not available, do each part yourself in sequence and keep each one narrow.
4. Write `research.md`: the questions, then facts, each with `file:line` or a doc link. No recommendations.

## Part 2 — options.md
1. Now read the spec and `research.md` together.
2. Write 2–3 options. Each option has: description, where the change goes, risks, data/migration impact,
   operating cost, rollback, how to verify, and fit with existing ADRs (cite them).
3. The human chooses. Record the choice and the reason at the top of `options.md`.
4. If the choice is an architecture decision, draft an ADR at
   `<paths.work>/<TICKET>-<slug>/drafts/adr-<slug>.md` with frontmatter `kind: adr`, `title`,
   `status: proposed`, and sections: Context · Options considered (from options.md) · Decision ·
   Consequences (good / bad / to watch) · How to check the decision still holds. Never write into `<paths.adr>`
   yourself: `kuanflow promote` moves the draft after human review.
5. Optional (W10): if the research mapped an area of code worth keeping, save it as `<paths.wiki>/<topic>.md`
   with frontmatter `generated: true`, `source_commit` (current HEAD), `source_paths`, `reviewed_by:` (empty),
   `stale: false`, and `file:line` for every important claim.

## Output
`research.md` and `options.md` in the work folder; optional ADR draft in `drafts/`.
Gate: the human picks an option.

## Never
- Put proposals in `research.md`.
- Present a single option.
- Copy a deprecated pattern because it is the most common one.
