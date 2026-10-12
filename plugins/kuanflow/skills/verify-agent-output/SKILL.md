---
name: verify-agent-output
description: Use before claiming any task is done, before committing or opening a PR, and whenever reviewing a diff produced by an AI agent. Requires fresh command evidence for every success claim.
---
# Verify agent output

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Resolve the work item, in this order: env `KUANFLOW_WORK` (a path or ticket key) → the ticket key in the
   branch name, matched with `work.ticket_pattern` → the `work` field of `.kuanflow/state.json` → ask the human.
   The work folder is `<paths.work>/<TICKET>-<slug>/`. Never guess the work item.
3. Required keys: `commands.build`, `commands.verify`, `paths.work`. Optional: `commands.test`, `commands.lint`,
   `risk.fintech`, `protected_paths`. If a required key is missing, stop and ask the human; never guess a
   command.

## Hard rules
- Evidence before assertions: every "done/passing/fixed" claim cites a command run in THIS session plus its exit code/output.
- Never accept tests written in the same context as the code they test.
- Do not modify, skip, or delete existing tests to make them pass.
- Never edit files under `protected_paths`. This skill reviews; it does not fix. Report findings instead.

## Steps
1. Read spec.md. List every acceptance criterion (AC-xx) and map it to a test name. List unmapped ACs as FAIL.
   - spec.md is in the work folder. If it is missing, stop and ask.
2. Run and paste results: build, full test suite, linter, static analysis, secret scan.
   - Use the commands from config: `commands.build`, `commands.verify` (full suite), `commands.lint`.
   - A check with no configured tool (for example no secret scanner) is recorded as N/A with the reason, never PASS.
3. Diff audit against base branch:
   - Every new API/class/annotation exists in the dependency version actually declared (check source or docs, not memory).
   - Any test changed, @Disabled, assertion weakened, or deleted → flag.
   - Mocks returning the very value being asserted (tautological tests) → flag.
   - Files changed outside plan.md scope → flag.
   - Security: disabled TLS/validation, string-built SQL, secrets, PII in logs.
   - Copied deprecated patterns → flag.
   - Files under `protected_paths` modified (not created) → flag.
4. If the diff touches money, orders, accounts or settlement → run the fintech-review skill.
   - When `risk.fintech` is true, run fintech-review for every diff.
5. Answer explicitly: "What behavior would make me reject this even if tests are green?" Then check it.
6. Write review.md: one row per check, PASS/FAIL, evidence. Never summarize as "looks good".
   - Write it to `<paths.work>/<TICKET>-<slug>/review.md` using the format below.
   - Any FAIL means NOT READY. End with exactly one line: `Conclusion: READY` or `Conclusion: NOT READY`.

## review.md format
```markdown
# Review — <TICKET> — <commit range>

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Build | PASS | `<commands.build>` exit 0 |
| 2 | AC-01 → test | PASS | OrderIdempotencyTest#AC01_duplicateKeyReturnsSameOrder |
| 3 | AC-04 → test | FAIL | no test for partner timeout |
| 4 | APIs exist in declared versions | PASS | … |
| 5 | Existing tests changed/skipped | PASS | git diff shows no change to existing tests |
| 6 | PII in logs | FAIL | OrderController.java:88 logs the full request |

## "What behavior would make me reject this even if tests are green?"
## Conclusion: READY / NOT READY
```
