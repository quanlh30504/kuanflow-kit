---
description: W10 — Capture knowledge - postmortem, wiki, ADR/runbook drafts, skill and checklist updates
argument-hint: "[ticket-or-incident-id]"
---
Capture what we learned from $ARGUMENTS so the next time is faster.

If `w10` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `paths.wiki`,
   `knowledge.repo` and `workflows.enabled`.
2. Find the work folder `<paths.work>/$ARGUMENTS*` and read its artifacts (`review.md`, `incident-notes.md`,
   `plan.md`, `research.md`).
3. If the Superpowers skill `writing-skills` is installed, use it as well when you draft a skill change.
4. For each event below that happened in this work item, do the action. Propose; never merge or promote
   anything yourself.

| Event | Action |
|---|---|
| The agent made the same kind of mistake a second time | Propose a rule for the related skill or for `AGENTS.md` (outside the Kuanflow block), with the real example |
| Research mapped an area of code | Save it as `<paths.wiki>/<topic>.md` with `generated: true` and `source_commit` |
| An architecture option was chosen | Draft an ADR in `drafts/` (`kind: adr`); after human review, `kuanflow promote` moves it |
| Production incident | A postmortem is required: run write-postmortem |
| The same incident `category` happened 2–3 times | Propose a checklist item for fintech-review or verify-agent-output |
| A repeated operational task | Draft a runbook in `drafts/` (`kind: runbook`); after human review, `kuanflow promote` moves it |
| Generated wiki pages may be outdated | Run knowledge-gardening |

5. End with the list of proposals and where each one was written.
