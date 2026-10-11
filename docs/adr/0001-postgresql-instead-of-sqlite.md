# ADR-0001: PostgreSQL instead of SQLite

Status: accepted (Phase 3)

## Context

The starting application (ops-assistant) stored tasks in one SQLite file. OpsPilot's data is much more relational:
- services, incidents, deployments, logs, and metrics;
- agent runs, tool calls, and events;
- actions, approvals, and audit events.

Several of these require guarantees that SQLite either lacks or offers only in a weaker form:

- **Row locks across concurrent requests.** Two reviewers deciding the same approval must not both execute the action. `ApprovalRepository.decide` uses `SELECT … FOR UPDATE`.
- **Append-only records.** Database triggers reject `UPDATE`, `DELETE`, and `TRUNCATE` on `audit_events` and `agent_events` (migrations 011 and 013).
- **Vector search** for retrieval (see ADR-0002).
- **Statement timeouts** that bound slow queries (`DATABASE_STATEMENT_TIMEOUT_MS`).

## Decision

Use one PostgreSQL 16 database (the `pgvector/pgvector:pg16` image). Schema changes are versioned SQL migrations applied at startup.

## Alternatives considered

- **Keep SQLite.** Simple, with zero setup. Its locking is database-wide, triggers would work, but there is no pgvector, and a shared Compose service is awkward.
- **PostgreSQL plus an ORM or Alembic.** Adds an abstraction layer. Plain SQL migrations and `psycopg` keep every query visible.

## Reason

PostgreSQL provides the row-level locking, triggers, timeouts, and vector type that the approval, audit, and retrieval designs depend on. A single database keeps transactions simple: an approval decision, its simulated execution, the audit rows, and the agent events commit or roll back together.

## Tradeoffs

- Local setup now needs Docker or a Postgres install.
- Plain SQL migrations have no automatic down-migrations.

## Consequences

- There is one authoritative store. Tests use a separate `opspilot_test` database on the same server, and benchmarks use `*_bench` databases.
