---
description: W4 — Write plan.md - small phases, each with files, ACs, an exact verify command and a stop condition
argument-hint: "[ticket-id]"
---
Write the implementation plan for ticket $ARGUMENTS.

If `w4` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `commands.*` and
   `workflows.enabled`. If `commands.verify` or `commands.single_test` is missing, stop and ask.
2. Find the work folder `<paths.work>/$ARGUMENTS*`. Read `spec.md`, `research.md` and the chosen option in
   `options.md`. If no option has been chosen, stop and ask.
3. If the Superpowers skill `writing-plans` is installed, follow it as well. Where it differs from this
   command, the rules below and the project config win.
4. Write `plan.md` in that work folder with the template below. Every phase has:
   - a goal and the files it creates or changes;
   - the ACs it covers;
   - an exact verify command, built from `commands.verify` or `commands.single_test` (never guessed);
   - when to stop and ask;
   - a status box: `[ ] todo` / `[~] doing` / `[x] done`, plus notes.
5. Gate: no open questions left in the plan; each phase small enough to review in about 15 minutes. End by
   asking me to approve the plan.

Never: one giant phase; a phase without a verify command; a plan that edits existing tests to make them fit.

Template:

```markdown
---
ticket: <TICKET>
spec: <paths.work>/<TICKET>-<slug>/spec.md
option: <paths.work>/<TICKET>-<slug>/options.md#option-b
---
# Plan

## Phase 1 — <goal>   [ ] todo
- Files: …
- AC: AC-03
- Verify: <exact command from commands.single_test or commands.verify>
- Stop & ask if: …
- Notes:

## Phase 2 — <goal>   [ ] todo
- Files: …
- AC: AC-01, AC-02
- Verify: …
- Stop & ask if: the public API has to change

## Decisions log
## Status (update before every /clear)
```

Status values in the heading: `[ ] todo`, `[~] doing`, `[x] done`.
