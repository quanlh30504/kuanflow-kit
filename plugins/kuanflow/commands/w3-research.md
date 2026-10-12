---
description: W3 — Research the current code (facts with file:line) and compare 2–3 solution options
argument-hint: "[ticket-id]"
---
Run the research-solution skill for ticket $ARGUMENTS.

If `w3` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `paths.wiki`,
   `paths.adr`, `knowledge.repo` and `workflows.enabled`.
2. Find the work folder `<paths.work>/$ARGUMENTS*` and its `spec.md`. If missing, stop and ask.
3. Execute every step of research-solution: research questions first, `research.md` (facts only), then
   `options.md`. Use the codebase-locator, codebase-analyzer and pattern-finder subagents when available.
4. Write `research.md` and `options.md` in that work folder. End by asking me to choose an option; draft an
   ADR in `drafts/` only after I choose an architectural option.
