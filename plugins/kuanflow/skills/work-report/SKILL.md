---
name: work-report
description: Use at the end of the day or week to draft a work report (done with evidence links, in progress, blockers, risks, next) in the personal reports folder. Do not use for incident reports or postmortems.
---
# Work report (W9)

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
   Also read `~/.kuanflow/config.yaml` if it exists.
2. No project key is required. Optional: `paths.work` (open plans) and `integrations.jira_project_key`. Ask
   whether the report is daily or weekly if the request does not say. If a source you need (ticket tracker,
   git host) is missing or not connected, stop and ask the human to connect it or paste the data.

## Inputs
- My commits (`git log` filtered by my git author), my PRs and their state, ticket status.
- `plan.md` of open work folders (`<paths.work>/*/plan.md`), to report progress by phase.
- This period's journal under `~/.kuanflow/journal/`.

## Steps
1. Collect the inputs with tools and commands.
2. Group into: Done · In progress · Blocked / need help · Risks · Next.
3. Every Done item links its evidence (PR, ticket, commit). An item without evidence goes to In progress.
4. In progress shows progress by phase from `plan.md` (for example "Phase 2/4").
5. The human edits the tone before sending.

## Never
- Exaggerate, or report work as done without a link.
- Include personal or customer data.

## Output
- Daily: `~/.kuanflow/reports/YYYY-MM-DD.md`
- Weekly: `~/.kuanflow/reports/YYYY-Www.md` (ISO week, for example `2026-W45.md`)

```markdown
# Report — 2026-W45

## Done
- [ORD-123] Idempotent POST /orders — PR #456 (merged)

## In progress
- [ORD-130] Settlement retry — Phase 2/4

## Blocked / need help

## Risks

## Next
```
