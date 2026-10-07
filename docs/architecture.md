# Architecture

OpsPilot is a single Next.js frontend and a single FastAPI backend backed by PostgreSQL. One manual Ops Agent loop uses registered deterministic read-only tools and knowledge retrieval to investigate incidents. The backend evaluates proposals with its policy engine, persists approval state, and invokes only the controlled simulator after a permitted human approval.

Agent runs, tool calls, actions, approvals, simulated operational state, and audit events are stored in PostgreSQL. The audit trail uses an append-only table protected by database triggers against update, delete, and truncate. `GET /audit/incidents/{incident_id}` joins incident events with events for linked agent runs to present a reconstructable incident timeline.

Each simulator action stores a unique idempotency key derived from its run, action type, and normalized target. Repeating the same committed approval request returns its saved execution result without rerunning the simulator or duplicating audit events.

The agent applies bounded timeouts around Gemini decisions, knowledge retrieval, and deterministic tool calls. PostgreSQL connections and statements have explicit time limits. Only known transient faults are retried, once, with a short backoff. Tool failures and malformed results are passed back as structured failed evidence; the loop may use other tools before returning an uncertain or escalated run. Timed-out synchronous read tools run in worker threads and cannot be forcefully stopped, so database statement timeouts and read-only tool classification bound their remaining work.

The simulator is the only action target. No production infrastructure is connected. The application uses one backend and one database; it does not use a separate audit service or distributed event bus.

OpsBench v1 is a versioned JSON scenario set with deterministic setup controls for injected faults, roles, approval decisions, and verification outcomes. Its CLI validates definitions and confirms stable repeated loads without invoking a model or changing simulator state.

Phase 21 adds a security boundary around the model/tool interface. The Gemini prompt labels user requests, retrieved knowledge, logs, metrics, and tool results as untrusted data and instructs the model not to expose secrets. The agent advertises only READ tools and rejects a selected tool whose registered kind is not READ. Policy remains server-side, and high-risk operator proposals pause for human approval. Dedicated adversarial tests cover prompt and log injection, viewer rollback denial, approval bypass, and secret-exposure requests. These tests exercise deterministic code and do not guarantee live-model behavior.

Phase 22 records the actual agent lifecycle in immutable PostgreSQL `agent_events`. Model decisions, retrieval, tool calls, action proposals, policy, approval, simulator execution, verification, and run state transitions carry structured timestamps/status and durations where measurable. Authenticated `GET /agent/runs/{run_id}/events` returns the ordered trace; viewers are limited to their own runs while operators/admins can inspect runs. A future UI can visualize this API. No animation, OpenTelemetry, or distributed tracing stack is used. The backend suite passes 74 tests, including a complete trace reconstruction and event immutability check.
