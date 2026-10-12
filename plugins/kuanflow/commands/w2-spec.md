---
description: W2 — Write a verifiable spec.md (Given/When/Then ACs, contracts, NFRs) from answered questions
argument-hint: "[ticket-id]"
---
Run the write-spec skill for ticket $ARGUMENTS.

If `w2` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `risk.fintech` and
   `workflows.enabled`.
2. Find the work folder `<paths.work>/$ARGUMENTS*` and its `questions.md`. If either is missing, or a blocking
   question has no answer, stop and ask.
3. Execute every step of write-spec.
4. Write `spec.md` in that work folder with `status: draft`. End with the AC list and anything I must decide.
