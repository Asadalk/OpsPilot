# Architecture decision records

Each record states the context, the decision, the alternatives considered, the reasons, the tradeoffs, and the consequences.

| ADR | Decision |
|---|---|
| [0001](0001-postgresql-instead-of-sqlite.md) | PostgreSQL instead of SQLite |
| [0002](0002-pgvector-instead-of-a-vector-database.md) | pgvector (with hashed bag-of-words vectors) instead of a separate vector database |
| [0003](0003-single-agent.md) | One agent with a manual loop |
| [0004](0004-deterministic-policy-engine.md) | A deterministic, server-side policy engine decides actions |
| [0005](0005-human-approval-for-high-risk-actions.md) | Human approval for high-risk actions |
| [0006](0006-simulated-operations-environment.md) | A simulated operations environment, not real infrastructure |
| [0007](0007-synchronous-agent-runs.md) | Run investigations synchronously (no job queue in v1) |
| [0008](0008-no-live-streaming.md) | Show the stored trace instead of streaming live progress |
