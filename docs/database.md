# Database

There is one PostgreSQL 16 database with the `vector` extension (`pgvector/pgvector:pg16`). The schema comes from ordered SQL files in `backend/migrations/` (001–016). The backend applies any that are missing at startup, and records each one in `schema_migrations`.

## Tables

### Simulator (what the tools read and the actions change)

| Table | Key columns | Notes |
|---|---|---|
| `services` | `id`, `name` (unique), `environment`, `repository`, `current_state`, `fault` | `current_state` is healthy, degraded, or failed. `fault` is hidden ground truth that no API or tool selects (migration 015). |
| `incidents` | `id`, `title`, `severity`, `status`, `service_id` → services, `created_at`, `updated_at` | Resolved only by a SUCCESS verification. |
| `deployments` | `deployment_id`, `service_id` → services, `version`, `deployed_at`, `author`, `status` | A rollback marks the current release `rolled_back`. |
| `logs` | `id`, `timestamp`, `service_id` → services, `level`, `message`, `trace_id` | |
| `metrics` | `id`, `timestamp`, `service_id` → services, `metric_name`, `value` | Verification compares the latest values before and after an action. |

### Knowledge

| Table | Key columns | Notes |
|---|---|---|
| `knowledge_documents` | `id`, `source` (unique), `document`, `category`, `ingested_at` | Re-ingestion replaces a document's chunks. |
| `knowledge_chunks` | `id`, `document_id` → knowledge_documents (cascade), `chunk`, `content`, `embedding vector(128)` | Hashed bag-of-words vectors (see ADR-0002). |

### Agent runs and decisions

| Table | Key columns | Notes |
|---|---|---|
| `agent_runs` | `run_id` (uuid), `user_request`, `service`, `severity`, `status`, `diagnosis`, `evidence`, `hypotheses`, `hypothesis_history`, `knowledge_citations`, `action_proposal`, `policy_decision`, `created_at`, `completed_at` | `status`: investigating, paused, completed, or failed. |
| `agent_tool_calls` | `id`, `run_id` → agent_runs, `call_index`, `tool`, `arguments`, `start_time`, `end_time`, `result`, `success`, `error` | One row per tool call, including failures. |
| `agent_events` | `event_id`, `run_id` → agent_runs, `event_type`, `occurred_at`, `duration_ms`, `model`, `tool`, `status`, `error`, `details` | The run timeline. Append-only (triggers reject UPDATE, DELETE, TRUNCATE). Token counts are stored in `details` on model-decision events. |
| `actions` | `action_id`, `run_id` → agent_runs, `proposal`, `status`, `result`, `idempotency_key` (unique), `created_at`, `executed_at` | The key is `run_id:action_type:target`. `result` holds the execution and verification output. |
| `approvals` | `id`, `run_id` (unique) → agent_runs, `action_id` (unique) → actions, `requested_by`, `requested_at`, `expires_at`, `decision`, `decided_by`, `decided_at`, `reason` | `decision`: pending, approved, rejected, or expired. `decided_by` is `policy:<user>` when policy allowed the action without a human. |
| `audit_events` | `event_id`, `occurred_at`, `actor`, `event_type`, `entity_type`, `entity_id`, `run_id`, `reason`, `result`, `details` | The incident story (login, proposals, policy, approvals, execution, verification, resolution). Append-only (triggers reject UPDATE, DELETE, TRUNCATE). |

### Legacy

| Table | Notes |
|---|---|
| `tasks` | The original task-extraction feature (`/extract`, `/tasks`). |

## Relationships

```text
services ─┬─< incidents
          ├─< deployments
          ├─< logs
          └─< metrics

knowledge_documents ─< knowledge_chunks

agent_runs ─┬─< agent_tool_calls
            ├─< agent_events
            ├─< actions ─── approvals (1:1 per run and per action)
            └── (audit_events reference run_id without a foreign key, so the history survives run cleanup)
```

## Transactions that matter

- **An approval decision** locks the approval row (`FOR UPDATE`). The simulator action, the verification, the approval update, the action update, the incident resolution, and the audit and agent events then commit together, or not at all.
- **Creating a pending approval** locks the run row, so the same run cannot create two approvals.

## Other databases on the same server

- `opspilot_test`: used by the test suite. The suite refuses any name that does not end in `_test`.
- `*_bench`: OpsBench and failure-injection runs. The runner refuses to reset any database whose name does not end in `_bench`.
