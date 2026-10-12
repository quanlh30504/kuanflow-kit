---
id: INC-0042
title: Duplicate orders created when retrying the settlement call
date: 2026-11-03
severity: SEV2
services: [order-service, settlement-service]
category: <one category from taxonomy.md>
signatures:
  - "DuplicateKeyException: order_ref"
  - "Timeout calling settlement-service after 3000ms"
detection: alert
duration_minutes: 42
customer_impact: "~120 orders showed an error; no duplicate trade was executed"
fix_pr: <link>
regression_test: OrderRetryIdempotencyTest
related_adr: [0007]
status: draft | approved
---
## Summary (2–3 sentences)

## Impact

## Timeline (Vietnam time)

## Detection

## Root cause (5 whys)

## Why it was not detected earlier

## Mitigation

## Fix and regression test

## What went well / what did not

## Action items (owner, due date)

## Lessons → which skill or checklist to update

> Blameless: describe systems and processes, not individuals. Personal data removed before commit.
