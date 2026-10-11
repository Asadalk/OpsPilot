# ADR-0004: A deterministic, server-side policy engine decides actions

Status: accepted (Phase 12)

## Context

The model proposes remediations. Model output can be wrong, manipulated through prompt injection in logs or runbooks, or simply over-eager. Something has to decide whether a proposal may run.

## Decision

`PolicyEngine.evaluate` (`app/policy/engine.py`) decides `allow`, `deny`, or `require_approval` from four inputs:

- the requester's JWT role;
- the canonical risk of the action, from the server table `RISK_BY_ACTION` (the risk the model claims is ignored);
- the service's environment, as stored in the database;
- the customer configuration, which can only make a decision stricter (ADR-0006).

`POLICY_RULES` is an explicit table: (role, risk) → outcome in production and outcome elsewhere.

## Alternatives considered

- **Let the model decide**, either by asking it whether an action is safe or by trusting the risk level it states.
- **An external policy language** (for example OPA/Rego).
- **Hard-coded `if` statements** spread through the code.

## Reason

Authorization must not depend on text the model produced. Tests prove this: a proposal labelled `LOW` by the model is still evaluated as `HIGH` for a restart, and a viewer is denied. A small table in Python is easy to read and to test exhaustively; a test checks that every role and risk pair has a rule. A separate policy language would add a runtime and a new syntax for 12 rules.

## Tradeoffs

- Rules change through code review and redeployment, not at runtime.
- The table is coarse. It is per role and risk, not per individual action or user.

## Consequences

- The agent can only *propose*. Proposals withheld for incomplete evidence never reach policy.
- `allow` for a simulator action executes through the same recorded path as a human approval. It is recorded as `policy:<user>` (ADR-0005).
