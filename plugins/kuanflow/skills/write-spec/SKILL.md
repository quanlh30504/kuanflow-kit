---
name: write-spec
description: Use after the clarification questions for a ticket have been answered, to write a verifiable spec.md with acceptance criteria (Given/When/Then), API/event contracts and numeric NFRs. Do not use while blocking questions are still open.
---
# Write spec (W2)

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Resolve the work item, in this order: env `KUANFLOW_WORK` (a path or ticket key) → the ticket key in the
   branch name, matched with `work.ticket_pattern` → the `work` field of `.kuanflow/state.json` → ask the human.
   The work folder is `<paths.work>/<TICKET>-<slug>/`.
3. Required keys: `paths.work`, `risk.fintech`. If a required key is missing, stop and ask the human.
4. Read `questions.md` in the work folder. If it is missing, or a blocking question has no answer, stop and ask:
   the spec must not fill gaps with guesses.
5. Template: use `.kuanflow/templates/spec.md` if the project has one; otherwise `templates/spec.md` in this
   skill's directory.

## Steps
1. Write user stories and acceptance criteria in **Given/When/Then** form. Number them `AC-01`, `AC-02`, …
2. Describe the API/event contract: request, response, error codes, event schema, versioning.
3. State NFRs with numbers: p99 latency, throughput, partner SLA.
4. If `risk.fintech` is true, fill the fintech section: idempotency key, duplicate handling, transaction
   boundary, audit log, masking of sensitive data in logs, rollback/compensation.
5. Write the **Out of scope** section to stop scope creep.
6. Copy the agreed assumptions from `questions.md`. Open questions must be empty before approval.
7. Set `status: draft`. The human reviews (ideally with the BA/QA) and sets `status: approved` and
   `approved_by`.

## Output
`<paths.work>/<TICKET>-<slug>/spec.md`.
Gate: every AC can be checked by an automated test or by a concrete manual step. Rewrite any AC that cannot.

## Never
- Invent answers to open questions.
- Write an AC that cannot be verified ("the system is fast", "handles errors properly").
