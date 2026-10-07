# Architecture

## Current Phase 4 structure

```text
frontend (Next.js)
    |
    v
backend/app/main.py (FastAPI application)
    |
    +-- app/api/routes/tasks.py
    |       validates request and maps domain failures to HTTP responses
    +-- app/services/gemini.py
    |       calls Gemini and validates model-shaped data
    +-- app/services/rag.py
    |       performs deterministic lexical guideline retrieval
    +-- app/services/tasks.py
    |       coordinates task use cases
    +-- app/db/repositories.py
    |       owns task persistence operations
    +-- app/db/database.py
    |       owns PostgreSQL connections and migration application
    +-- app/models/schemas.py
    |       owns Pydantic request, model-output, and response schemas
    +-- app/core/config.py
            owns environment-backed settings

PostgreSQL currently contains the original `tasks` table plus the operational domain tables created by `002_operational_domain.sql`: `services`, `incidents`, `deployments`, `logs`, and `metrics`. Incidents, deployments, logs, and metrics reference `services.id` with foreign keys. Seed rows make the domain queryable immediately after an empty database is migrated.

The deterministic simulator data is created by `003_ops_simulator.sql`. The read-only simulator routes use `app/db/simulator.py` and `app/services/simulator.py`; they query PostgreSQL directly through the repository boundary and never call Gemini.

Phase 6 adds `app/tools`: `Tool` defines typed input/result schemas and explicit execution errors, `registry.py` builds the available tools, and `operational.py` implements the six read-only tools. The tools call the simulator repository directly and are independently executable without FastAPI or Gemini.

Phase 7 adds one direct `OpsAgent` loop. `GeminiDecisionProvider` chooses a registered tool or a final diagnosis, `OpsAgent` executes the selected read-only tool, and `agent_runs` plus `agent_tool_calls` store the request, evidence, timing, arguments, results, failures, and diagnosis. No write-capable tool is registered.

Phase 8 adds `knowledge_documents` and `knowledge_chunks` with pgvector embeddings. `app/rag/ingest.py` cleans and chunks Markdown, creates fixed 128-dimensional hashed-token embeddings, and stores them in PostgreSQL. Exact cosine similarity retrieves bounded chunks with provenance. The agent performs an initial retrieval and persists citations; knowledge supports runtime evidence and cannot authorize actions.
```

`backend/main.py`, `backend/models.py`, `backend/database.py`, and the old service and route paths are compatibility shims. The container starts `app.main:app` directly.

## Request flow

`POST /extract` validates the request, retrieves relevant guideline chunks, asks Gemini for structured output, validates every extracted task, calls the task service, and persists through the repository. `GET`, `PATCH`, and `DELETE /tasks` use the same service and repository path. Routes do not issue SQL.

PostgreSQL is the sole persistence system.

## Future additions

Later phases may add deterministic operational tools, policy, approvals, simulated execution, audit records, and evaluation. Those additions must remain inside this single backend and database boundary.