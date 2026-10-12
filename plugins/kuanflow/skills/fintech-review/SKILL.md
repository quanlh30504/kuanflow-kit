---
name: fintech-review
description: Use when a diff touches money amounts, orders, trades, accounts, balances, settlement, reconciliation, or calls to payment/exchange/partner systems.
---
# Fintech review checklist

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Required keys: `risk.fintech`, `paths.work`. If a required key is missing, stop and ask the human.
3. If `risk.fintech` is false and the diff does not touch money, orders, accounts or settlement, write
   "Fintech review: skipped (`risk.fintech` is false)" and stop. Otherwise run the full checklist.
4. You need the diff against the base branch and `spec.md` of the work folder. Read code; do not trust the
   description of the change.

For each item: PASS / FAIL / N/A with file:line evidence.

## Money & precision
- Monetary values use BigDecimal (or minor-unit long) with explicit scale and RoundingMode; no float/double.
- Currency is explicit; no implicit conversion.

## Idempotency & duplicates
- Every externally-triggered write has an idempotency key with a uniqueness constraint.
- Retry path cannot create a second order/transfer. A test calls the endpoint twice with the same key.

## Consistency
- Transaction boundaries are explicit; no remote call inside a DB transaction without outbox/compensation.
- State transitions validated against allowed transitions; terminal states are final.
- Concurrency: optimistic/pessimistic locking where two requests can touch the same balance/order.

## Time
- Timezone explicit (Asia/Ho_Chi_Minh vs UTC); trading session, holidays, cut-off, T+n handled.

## Partner calls
- Timeouts set; retries bounded with backoff; unknown outcome (timeout after send) handled via status query/reconciliation.

## Audit & data protection
- Audit log for state changes (who, what, when, before/after).
- No PII, account numbers, tokens in logs or error messages; masking applied.

## Reconciliation
- Change keeps or extends reconciliation data; a mismatch is detectable.

## Output
Append a `## Fintech review` section to `review.md` in the work folder: one table row per item above
(`Item | Result | Evidence`). N/A needs a reason. Any FAIL makes the whole review NOT READY.
