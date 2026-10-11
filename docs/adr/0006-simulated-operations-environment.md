# ADR-0006: A simulated operations environment, not real infrastructure

Status: accepted (Phase 5; faults added in the Phase 23 revalidation)

## Context

OpsPilot must demonstrate investigation, remediation, and verification. Connecting a model-driven system to real servers, clouds, or Kubernetes would be risky. It would also make results unreproducible and require real credentials.

## Decision

All tools read from, and all actions act on, simulator tables in PostgreSQL: services, incidents, deployments, logs, and metrics.

Each degraded scenario service has a hidden `fault` column. No tool or API selects it. Only the matching action clears it: restart for a crashed process or an exhausted connection pool, rollback for a bad deployment, and nothing for an external dependency. Verification therefore compares real before and after state.

Customer-specific scope and policy come from configuration (`CUSTOMER_CONFIG`), not code. That is the same platform with different settings, with no multi-tenant infrastructure.

## Alternatives considered

- **Real or containerized infrastructure** (Docker restarts, a toy Kubernetes cluster). More realistic, but non-deterministic, slow to reset, and a real blast radius.
- **Pure mocks in tests.** Deterministic, but no persistent state and no end-to-end behavior to verify.

## Reason

- Deterministic worlds make OpsBench reproducible (two runs produce identical results), and each scenario resets in milliseconds.
- Hidden faults let verification fail meaningfully, so a wrong action is detected instead of being assumed to work.
- There are no credentials and no destructive capability.

## Tradeoffs

- Faults are designed rather than organic. The simulator tests known patterns, not the messiness of production.
- Execution realism is limited. A "restart" is a state change, not a process restart.

## Consequences

- The integration boundary is clear. A real deployment would replace `SimulatorActionRepository` and the read tools with real adapters behind the same policy, approval, and verification path.
- Any claim about production readiness is out of scope.
