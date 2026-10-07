# Architecture

OpsPilot is a single Next.js frontend and a single FastAPI backend backed by PostgreSQL. One manual Ops Agent loop uses registered deterministic read-only tools and knowledge retrieval to investigate incidents. The backend evaluates proposals with its policy engine, persists approval state, and invokes only the controlled simulator after a permitted human approval.

Agent runs, tool calls, actions, approvals, simulated operational state, and audit events are stored in PostgreSQL. The audit trail uses an append-only table protected by database triggers against update, delete, and truncate. `GET /audit/incidents/{incident_id}` joins incident events with events for linked agent runs to present a reconstructable incident timeline.

The simulator is the only action target. No production infrastructure is connected. The application uses one backend and one database; it does not use a separate audit service or distributed event bus.
