# Deployment

OpsPilot runs locally with Docker Compose. It has three services, and no worker or queue is needed (ADR-0007).

| Service | Image | Port | Health |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5433 → 5432 | `pg_isready` |
| `backend` | `./backend` (Python 3.11, FastAPI) | 8000 | `GET /health` |
| `frontend` | `./frontend` (Next.js production build) | 3000 | backend must be healthy first |

## First run

```bash
git clone https://github.com/Asadalk/OpsPilot.git && cd OpsPilot
cp backend/.env.example backend/.env       # set GROQ_API_KEY, or set LLM_PROVIDER=mock to run without a key
docker compose up --build
```

Open http://localhost:3000 and sign in as `operator`/`operator`. Approvals need a different user, such as `admin`/`admin`.

On startup the backend:
1. checks its settings (when `ENVIRONMENT` is not `development`, it refuses default credentials);
2. applies the migrations;
3. ingests `/knowledge`.

## Configuration (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq`, `gemini`, or `mock` |
| `GROQ_API_KEY`, `GROQ_MODEL` | none, `openai/gpt-oss-120b` | Groq access |
| `GROQ_TOKENS_PER_MINUTE` | `8000` | client-side pacing (free tier is 8000; Developer tier is 250000) |
| `MOCK_LLM_MODE` | `normal` | `timeout`, `malformed`, or `unavailable` for failure demos |
| `CUSTOMER_CONFIG` | unset | path to a customer TOML file, such as `/app/config/customers/acme-payments.toml` |
| `LLM_TIMEOUT_SECONDS`, `TOOL_TIMEOUT_SECONDS`, `RETRIEVAL_TIMEOUT_SECONDS` | 25, 5, 5 | per-step timeouts |
| `JWT_SECRET`, `AUTH_USERS_JSON` | development values | replace both, and set `ENVIRONMENT` to anything other than `development`, outside local use |

## Data

- PostgreSQL data lives in the `postgres_data` volume and survives `docker compose down` and `up`.
- `docker compose down -v` deletes it. The next start re-seeds the simulator from the migrations.

## Checks without the UI

```bash
docker compose exec backend pytest -q tests                  # test suite (separate test database)
docker compose exec backend python -m app.demo.failures all  # failure-injection cases
```
