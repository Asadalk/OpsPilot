# Architecture

## Current Phase 2 structure

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
    |       owns SQLite connections and schema initialization
    +-- app/models/schemas.py
    |       owns Pydantic request, model-output, and response schemas
    +-- app/core/config.py
            owns environment-backed settings
```

`backend/main.py`, `backend/models.py`, `backend/database.py`, and the old service and route paths are compatibility shims. The container starts `app.main:app` directly.

## Request flow

`POST /extract` validates the request, retrieves relevant guideline chunks, asks Gemini for structured output, validates every extracted task, calls the task service, and persists through the repository. `GET`, `PATCH`, and `DELETE /tasks` use the same service and repository path. Routes do not issue SQL.

## Future additions

Later phases may add deterministic operational tools, policy, approvals, simulated execution, audit records, and evaluation. Those additions must remain inside this single backend and database boundary.