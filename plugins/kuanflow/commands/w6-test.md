---
description: W6 — Write tests from the spec's acceptance criteria in a separate context (test-writer)
argument-hint: "[ticket-id]"
---
Write tests from the spec for ticket $ARGUMENTS.

If `w6` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `paths.work`, `commands.test`,
   `commands.single_test` and `workflows.enabled`.
2. Find the work folder `<paths.work>/$ARGUMENTS*` and its `spec.md`. If missing, stop and ask.
3. Delegate to the test-writer subagent: it reads `spec.md` and public interfaces only, never the
   implementation. Without subagents, do it yourself in a fresh context that has not seen the implementation.
4. If the Superpowers skill `test-driven-development` is installed, follow it as well. Where it differs from
   this command, the rules below win.

Rules:
- Tests check the requirement, not the assumptions of the code.
- Every AC has at least one test; the test name or a comment carries the AC id.
- Always cover: boundaries (0, negative, max, rounding), errors (timeout, partner 5xx), duplicates (the same
  idempotency key twice), concurrency (two requests in parallel), time (outside the session, holidays).
- Prefer the lowest level that reproduces the behaviour: unit, then component/integration, then end-to-end.
- No tautologies: a mock must not return the very value the test asserts.
- Run the new tests with `commands.single_test` or `commands.test` and show the result (failing before the
  implementation exists is expected).

Output: the tests, plus an AC → test map and the coverage of new code, appended to `plan.md` under
`## Test map`.
