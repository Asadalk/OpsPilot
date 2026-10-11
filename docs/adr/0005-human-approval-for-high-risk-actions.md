# ADR-0005: Human approval for high-risk actions

Status: accepted (Phases 13–14)

## Context

Restarts and rollbacks change service state. Even a correct diagnosis can recommend the wrong action. In the OpsBench verification-failure category, the requester pushes a restart that does not fix the fault.

## Decision

When policy returns `require_approval`, OpsPilot stores the proposal as a pending approval in PostgreSQL (`approvals` and `actions`) and pauses the run. A different person with the operator or admin role must approve or reject it:

- **Requester cannot decide:** the person who requested the action gets HTTP 403 (`approvals.requested_by`).
- **Approve:** runs the simulator action, then verification (`SUCCESS`, `FAILED`, or `INCONCLUSIVE`, with at most one automatic retry). Incidents are resolved only on `SUCCESS`.
- **Reject or expire:** the run closes without executing anything.

A replayed approval returns the stored result without executing again (idempotency key `run_id:action_type:target`).

## Alternatives considered

- **Execute automatically, then notify a human.** The action has already happened.
- **Ask for confirmation inside the chat or LLM loop.** That puts authority back into the model conversation.
- **Keep approval state in memory.** It would be lost on restart, and the approval could be approved twice.

## Reason

The pause point sits before the side effect, and its state survives restarts. Tests cover timeout, duplicate decisions, unauthorized users, self-approval, and a lost response on retry. Measured: in the no-verification ablation, 6 of 8 wrong remediations were reported as resolved. With verification, none were.

## Tradeoffs

- A human in the loop adds latency to remediation.
- Approval fatigue is possible. The policy table keeps approvals to HIGH and CRITICAL actions only.

## Consequences

- Every executed action has a durable record: the approval, the action, its audit events, and its agent events.
- `allow` decisions use the same execution path, recorded as `policy:<user>`, so the trace never hides who authorized an action.
