---
description: W7 — Debug a bug or incident - reproduce first, competing hypotheses, evidence, then fix
argument-hint: "[ticket-or-incident-id]"
---
Debug $ARGUMENTS.

If `w7` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `paths.scratch`,
   `debug.services`, `debug.allow_prod_log_access`, `debug.budget`, `commands.*` and `workflows.enabled`.
2. Production alert, incident or error spike: run the debug-incident skill (full harness) with work folder
   `<paths.work>/$ARGUMENTS-<slug>/` (ask me for the slug if the folder does not exist).
3. Ordinary bug with an unknown cause: follow these steps (and the Superpowers skill `systematic-debugging`
   too, if it is installed):
   1. Look up postmortems and wiki pages for the error signature and the service.
   2. Reproduce with a failing test or script. No reproduction, no fix.
   3. List at least 2 competing hypotheses, each with a test that could disprove it.
   4. Run those tests and record the results.
   5. Root cause with 5 whys, down to why it was not caught earlier.
   6. Fix, plus a regression test. Run `commands.verify`.
   7. Continue with W8 (verify), then W10 (postmortem if it was an incident).
4. Write notes to `incident-notes.md` in the work folder. Keep logs and other sensitive data in
   `<paths.scratch>/$ARGUMENTS/` only.
