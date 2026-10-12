---
name: daily-plan
description: Use at the start of the working day, or when asked "what should I work on today?". Proposes a top-3 plan with blockers and early questions and writes it to the personal journal. Do not use to plan the phases of a single task (that is plan.md, W4).
---
# Daily plan (W0)

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
   Also read `~/.kuanflow/config.yaml` if it exists (personal preferences, outside any repo).
2. No project key is required. Optional: `integrations.jira_project_key` (to filter tickets) and `paths.work`
   (to find open plans). If a source you need is missing or not connected (ticket tracker, git host), stop and
   ask the human to connect it or paste the list. Never invent tickets, PRs or meetings.

## Inputs
- Yesterday's journal under `~/.kuanflow/journal/` and the latest report under `~/.kuanflow/reports/`.
- Open tickets assigned to me (tracker tool or MCP, read-only).
- My open PRs, PRs waiting for my review, and their CI status.
- `plan.md` of open work folders (`<paths.work>/*/plan.md`) in each open worktree.
- Meetings, only if the human allowed calendar access.

## Steps
1. Collect the inputs with tools and commands; do not reason about them yet.
2. Classify every item: blocking someone else > near deadline > in progress > new.
3. Propose a top 3, each with an estimate and a deep-work slot that avoids meetings.
4. List the questions that should go out early, so others can answer them today.
5. Write the journal file. The human confirms or edits the top 3 and creates the worktree for item 1.

## Never
- Decide priorities on your own: the top 3 is a proposal until the human confirms it.
- List ten "priorities", or leave out blockers.

## Output
`~/.kuanflow/journal/YYYY/MM/YYYY-MM-DD.md` (personal journal, outside the repo because it spans projects):

```markdown
# Daily — 2026-11-03

## Top 3
1. [TICKET-123] Implement idempotency for POST /orders — Phase 2/4 — ~3h — deep work 9:00–12:00
2. [PR #456] Review for A — ~45m — before 14:00 (blocks the release)
3. [TICKET-130] Send clarification questions to the BA — ~30m

## Blocked / waiting for others
- TICKET-128: waiting for the partner sandbox

## Questions to send early
- BA: what happens to an order that arrives after the ATC session?

## Notes
```
