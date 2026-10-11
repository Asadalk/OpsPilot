# Troubleshooting

Each entry below is a failure seen while building OpsPilot.

| Symptom | Cause | Fix |
|---|---|---|
| Backend restarts in a loop with `Name or service not known` | The Postgres container is not running | `docker compose up -d`. Postgres now has `restart: unless-stopped`. |
| Backend exits with `Knowledge directory not found` | `KNOWLEDGE_DIR` is set but the folder is not mounted | Run from the repository root so Compose mounts `./knowledge`, or unset `KNOWLEDGE_DIR` |
| Backend exits with `Refusing to start with ENVIRONMENT=…` | Default JWT secret or development accounts outside development | Set a long `JWT_SECRET` and real `AUTH_USERS_JSON`, or use `ENVIRONMENT=development` locally |
| Run fails with `GroqError: Groq HTTP 429 … tokens per minute` | Provider rate limit | Lower `GROQ_TOKENS_PER_MINUTE` to your plan's limit; the client paces itself and honors `retry-after` |
| Run fails with `429 … tokens per day (TPD)` | Free-tier daily token budget used up | Wait for the budget to refill (it refills continuously), or upgrade the plan |
| Run fails with `malformed_model_response` and `jsonschema: '/…'` in the run timeline | The model's JSON did not match the decision schema | The stored reason names the field. Check that `GROQ_DECISION_SCHEMA` covers every tool argument (a test enforces this). |
| Run fails with `llm_failure: ConnectionError … ConnectError` | DNS or network outage between the backend and the provider | Check connectivity. One retry is automatic; the run is marked failed, not successful. |
| Every tool call fails with `Service not managed for customer …` | `CUSTOMER_CONFIG` does not list that service | Add it to `[services] managed`, or unset `CUSTOMER_CONFIG` |
| Approve returns 403 `The requester cannot decide their own action` | Separation of duties | Sign in as a different operator or admin |
| Evaluation page shows "Not measured" | `backend/benchmarks/opsbench/v2/results/summary.json` does not exist | Run the benchmark, then `runner publish` |
| Tests stop with `Refusing to run tests against non-test database` | `TEST_DATABASE_URL` points at a database not ending in `_test` | Leave it unset (it defaults to `opspilot_test`) |
| `permission denied` editing files in `backend/benchmarks/...` | A container running as root wrote them | Run one-off containers with `--user 1000:1000`, or `chown` the files back |
| Frontend on port 3001 cannot reach the API | Port 3000 was busy and Next.js picked another port | Allowed: CORS accepts any `localhost` port |
| `docker compose build frontend` fails with a TypeScript error that `next dev` did not show | The production build type-checks; the dev server does not | Run `npx tsc --noEmit` before building; CI runs both |
