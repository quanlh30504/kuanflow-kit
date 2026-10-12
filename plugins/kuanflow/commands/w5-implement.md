---
description: W5 — Implement one phase of plan.md, verify it with the configured command, record status
argument-hint: "[ticket-id] [phase]"
---
Implement a phase of the plan for $ARGUMENTS (ticket key, then the phase number; the first `[ ] todo` phase if
no number is given).

If `w5` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `commands.*`,
   `protected_paths` and `workflows.enabled`.
2. Find the work folder `<paths.work>/<ticket>*` and its `plan.md`. If the plan is missing or not approved,
   stop and ask. Work on Phase k only; start from a fresh context that has loaded `plan.md`.
3. If the Superpowers skills `executing-plans` and `test-driven-development` are installed, follow them as
   well. Where they differ from this command, the rules below and the project config win.
4. For the phase:
   1. Mark it `[~] doing` in `plan.md`.
   2. If tests for its ACs exist (from W6), run them first and show them failing.
   3. Implement the minimum needed to make them pass.
   4. Run the phase's verify command and the related tests (`commands.single_test`, then `commands.verify`).
      Paste the command and its result; a phase is done only with that evidence.
   5. Mark it `[x] done` with notes, and make a small commit whose message describes the phase.
5. When the context is more than about 60% full, write the current state into the `## Status` section of
   `plan.md` (done, in progress, left, decisions) and ask me to clear the context.

Hard rules:
- Never modify, skip, or delete existing tests to make them pass.
- Never add a dependency the plan does not name; never change a public API outside the plan.
- Never edit files under `protected_paths`.
- Stop and ask when the phase's "Stop & ask if" condition happens, or when the plan turns out to be wrong.
