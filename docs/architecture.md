# Architecture

OpsPilot is one Next.js frontend, one FastAPI backend, and one PostgreSQL database (with the pgvector extension). A single agent loop investigates simulated incidents. Every write goes to a local simulator; no real infrastructure is connected.

```text
Next.js UI ──HTTP + JWT──> FastAPI
                             ├── Ops Agent (manual loop, one model call per step)
                             │     ├── READ tools ──────────> simulator tables
                             │     ├── hybrid retrieval ────> knowledge_chunks (pgvector)
                             │     └── LLM provider (Groq by default, Gemini optional)
                             ├── Policy engine (role × risk × environment)
                             ├── Approval service ──> simulator actions ──> verification
                             └── Audit + agent event writers
                                           │
                                     PostgreSQL (one database)
```

## Request flow for an investigation

1. `POST /agent/investigate` authenticates the bearer token and creates an `agent_runs` row.
2. Hybrid retrieval runs once for the request. Results with no shared terms and no keyword hit are dropped, so an unrelated query returns `empty` rather than three weak matches.
3. Each loop step sends one prompt to the configured model. The prompt labels the user request, evidence, and knowledge as untrusted data, lists only READ tools, and resends the current state in compact form.
4. The model returns a structured decision: either call one READ tool with arguments, or diagnose. The provider validates it against `AgentDecision`. Invalid output becomes a `malformed_model_response` failure, never a guess.
5. The application, not the model, runs the selected tool. Each call, its arguments, timing, and result are stored in `agent_tool_calls` and `agent_events`.
6. On a diagnosis with a proposed action, the server's policy engine decides `allow`, `deny`, or `require_approval` from the role, canonical risk, and service environment. Risk claimed by the model is ignored.
7. `require_approval` stores a pending approval and pauses the run. `allow` for a simulator action records the decision as `policy:<user>` and executes through the same path. `deny` records the outcome and executes nothing.
8. An approval decision runs the simulator action, captures before/after snapshots, verifies the result (`SUCCESS`, `FAILED`, `INCONCLUSIVE`), retries a failed action at most once, and resolves incidents only on `SUCCESS`.

## Model provider

`LLM_PROVIDER` selects Groq (default) or Gemini for both the agent and the legacy task extraction.

- **Groq** is called over plain HTTP with `httpx`, using Groq's OpenAI-compatible endpoint. No SDK is involved.
- The decision schema is non-strict JSON Schema with two allowed shapes. A tool call must name one of the advertised READ tools and include arguments. A diagnosis must include text. Groq validates the output against this schema, and Pydantic validates it again.
- `reasoning_effort: low` keeps gpt-oss output tokens small enough for the free-tier limit of 8,000 tokens per minute.
- A 429 response is retried once after Groq's `retry-after` delay, capped at 30 seconds.
- Provider-reported token counts are stored on each model-decision event. Cost is not computed.

## Simulator

The services, incidents, deployments, logs, and metrics tables are seeded by migrations. Each degraded scenario service has a hidden `fault` column that no read API or tool selects:

| Service | Fault | Fixed by |
|---|---|---|
| payments-api | connection_pool_exhaustion | restart |
| checkout-api | bad_deployment | rollback (an earlier good release exists) |
| auth-api | process_crash | restart |
| inventory-api | upstream_dependency (auth-api) | nothing on inventory itself |
| notification-api | external_dependency | nothing; escalate |

A mismatched action runs but leaves the symptoms in place, so verification fails, retries once, and escalates.

## Authorization and approval

JWT roles are `viewer`, `operator`, and `admin`. `POLICY_RULES` in `app/policy/engine.py` maps each (role, risk) pair to one outcome for production and one for other environments:

- Operators need approval for HIGH risk in production but not in staging.
- CRITICAL actions are never allowed in production.

The person who requested an approval cannot decide it. The API returns 403, and the UI hides the decision controls.

## Persistence and records

- `audit_events` and `agent_events` are append-only. Database triggers reject updates; `audit_events` also rejects deletes and truncates.
- The incident audit story is available at `GET /audit/incidents/{id}`. The ordered run trace is at `GET /agent/runs/{id}/events`.
- Action rows carry an idempotency key `run_id:action_type:target`. Replaying a committed approval returns the stored result without executing again.
- When an approval completes a run, its outcome is appended to the run's diagnosis, so the agent's evidence-based diagnosis is kept.

## Reliability

- Model calls, retrieval, tools, database connections, and statements all have bounded timeouts.
- Only transient failures are retried, once each. These are timeouts, connection errors, deadlocks, serialization conflicts, and HTTP 408, 429, or 5xx.
- A failed tool, empty data, or empty retrieval is recorded as uncertainty and is never treated as evidence of health.

## Startup and tests

- On startup the backend applies SQL migrations in order. If `KNOWLEDGE_DIR` is set, it then ingests that directory. Compose mounts `./knowledge` read-only at `/knowledge`. A missing directory stops startup.
- Tests run against a separate `opspilot_test` database on the same server, which is created if missing. The suite refuses any database name that does not end in `_test`, and it blanks LLM keys so tests never call a hosted model.

## Frontend

The Next.js pages are the dashboard, incidents, agent runs (event timeline), approvals, evaluation, sign-in, and the legacy task extraction and board.

- Every figure is read from the API. Values the saved evaluation does not measure are labeled as unmeasured.
- The dashboard success rate is a ratio of terminal run statuses. It is not the OpsBench task-success metric.
