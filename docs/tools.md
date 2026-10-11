# Tools

The tools are in `backend/app/tools/`. Each tool is a class with a `name`, `description`, `kind` (`read` or `write`), an input schema, and a result schema (all Pydantic). `Tool.run` validates the input and the output.

The errors are:
- `ToolInputError`: invalid arguments.
- `ToolExecutionError`: the service is unknown or outside the customer's scope, or the database is unavailable.
- `ToolResultError`: the tool returned data that does not match its result schema.

None of these tools needs a model.

## READ tools (the only tools the model is offered)

| Tool | Arguments | Returns |
|---|---|---|
| `get_service_health` | `service` | name, environment, repository, state |
| `get_metrics` | `service`, `limit` (1–100, default 20), `metric_name` (case-insensitive substring) | recent metric points |
| `search_logs` | `service`, `limit`, `query` (substring of the message), `level` | recent logs |
| `get_recent_deployments` | `service`, `limit` | deployments, newest first |
| `get_incident_history` | `service`, `limit` | incidents, including resolved ones |
| `search_runbooks` | `query`, `service` (optional), `mode` (`hybrid` (default), `semantic`, or `keyword`) | matched chunks with source, similarity, and content, plus status `ok` or `empty` |

## WRITE tools

| Tool | Purpose |
|---|---|
| `propose_action` | Builds a typed `ActionProposal` with the server-side risk level. Never offered to the model; the agent refuses it if the model selects it. |

## Actions and their server-side risk (`RISK_BY_ACTION`)

| Action | Risk | Executes against the simulator |
|---|---|---|
| `generate_report` | LOW | no |
| `create_incident`, `update_incident`, `create_github_issue` | MEDIUM | no (recorded only) |
| `restart_service`, `rollback_deployment` | HIGH | yes |
| `delete_data` | CRITICAL | never; denied in production for every role |

## Adding a tool

1. Write the input and result schemas in `tools/schemas.py`.
2. Subclass `Tool` (or `OperationalTool` for a service-scoped read), then register it in `tools/registry.py`.
3. If the Groq provider will call it, add its argument names to `GROQ_DECISION_SCHEMA` and to `TOOL_ARGUMENTS_SCHEMA` (Gemini). A test fails if a READ tool field is missing from either schema.
