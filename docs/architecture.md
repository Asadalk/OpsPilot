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
```

`backend/main.py`, `backend/models.py`, `backend/database.py`, and the old service and route paths are compatibility shims. The container starts `app.main:app` directly.

## Request flow

`POST /extract` validates the request, retrieves relevant guideline chunks, asks Gemini for structured output, validates every extracted task, calls the task service, and persists through the repository. `GET`, `PATCH`, and `DELETE /tasks` use the same service and repository path. Routes do not issue SQL.

PostgreSQL is the sole persistence system.

## Future additions

Later phases may add deterministic operational tools, policy, approvals, simulated execution, audit records, and evaluation. Those additions must remain inside this single backend and database boundary.