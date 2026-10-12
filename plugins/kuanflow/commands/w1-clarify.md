---
description: W1 — Clarify a requirement into questions, assumptions and edge cases before any design
argument-hint: "[ticket-id]"
---
Run the clarify-requirements skill for ticket $ARGUMENTS.

If `w1` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `work.ticket_pattern`,
   `risk.fintech` and `workflows.enabled`.
2. Find the work folder `<paths.work>/$ARGUMENTS*`. If there is none, create `<paths.work>/$ARGUMENTS-<slug>/`
   (ask me for the slug). Without a ticket, follow the skill's resolution order.
3. Execute every step of clarify-requirements. If `risk.fintech` is true, also use its fintech checklist.
4. Write `questions.md` in that work folder. End with the list of blocking questions that need an answer.
