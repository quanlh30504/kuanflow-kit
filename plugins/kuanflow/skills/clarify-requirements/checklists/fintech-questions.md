# Fintech clarification checklist

Use with clarify-requirements when `risk.fintech` is true. Turn every line that applies into a specific
question for this requirement. Skip lines that clearly do not apply and say why in one phrase.

## Money and precision
- Which amounts are involved (price, quantity, fee, tax, balance)? Scale and rounding mode for each? Which
  rounding applies at which step (per line, per order, per settlement)?
- Which currencies? Is any conversion needed, with which rate source and timestamp?
- Minimum and maximum values; what happens at zero and on negative values?

## Idempotency and duplicates
- What is the idempotency key for each externally triggered write? Who generates it?
- What must a duplicate request return (same result, conflict, error)? For how long are keys kept?
- Can the same event arrive twice from a queue or a partner callback?

## State
- What are the valid states and transitions? Which states are terminal?
- What happens to an order or transfer stuck in an intermediate state?

## Partners and failures
- Timeout per partner call? Retry policy and limits?
- Unknown outcome: the request was sent but no answer came back. Do we query the status, reconcile later, or
  mark it unknown? Who resolves it?
- Late or out-of-order partner responses: accepted, ignored, or flagged?

## Time and calendar
- Which timezone is the business time (Asia/Ho_Chi_Minh vs UTC) and which is stored?
- Trading sessions (ATO, continuous, ATC), cut-off times, behaviour outside the session.
- Holidays and non-business days: which calendar is the source of truth?
- Settlement cycle (T+n): which date is used for what?

## Limits and risk checks
- Which limits apply (per order, per day, per account)? Checked before or after reservation?
- What happens when two requests use the same balance at the same time?

## Reconciliation and reporting
- Which data must reconciliation see? How is a mismatch detected and who is alerted?
- Any regulatory or partner report affected by this change?

## Audit, security and personal data
- Which state changes need an audit record (who, what, when, before/after)?
- Which fields are personal data (account number, id number, phone, e-mail)? Where may they appear? They must
  never appear in logs or error messages.
- Who is authorised to perform each action? Any maker-checker (four-eyes) rule?

## Rollback and compensation
- If a later step fails, how is an earlier step compensated?
- Can the change be switched off (feature flag) without leaving orders or balances inconsistent?
