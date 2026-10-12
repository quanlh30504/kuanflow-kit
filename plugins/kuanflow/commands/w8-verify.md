---
description: W8 — Verify agent output against spec with evidence before commit/PR
argument-hint: "[ticket-id]"
---
Run the verify-agent-output skill for ticket $ARGUMENTS.

If `w8` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` for `commands.*`, `paths.work` and `risk.fintech`.
2. Find the work folder `<paths.work>/$ARGUMENTS*` (folder name starts with the ticket key) and its `spec.md`. If missing, stop and ask.
3. Execute every step of verify-agent-output. If `risk.fintech` is true, also run fintech-review.
4. Write `review.md` in that work folder. End with READY or NOT READY.
