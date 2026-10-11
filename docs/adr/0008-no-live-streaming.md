# ADR-0008: Show the stored trace instead of streaming live progress (v1)

Status: accepted

## Context

Every agent step is written to `agent_events` as it happens: retrieval, each model decision, each tool call, proposal, policy, approval, execution, verification, and completion. The run page renders that stored timeline.

Live streaming, for example over Server-Sent Events, would show steps while a run is in progress instead of after it finishes.

## Decision

Do not add streaming in v1. The incident page waits for the investigation request to return, then links to the run's stored timeline.

## Alternatives considered

- **Server-Sent Events** from `agent_events`: one-way, plain HTTP.
- **WebSockets:** bidirectional, which we do not need.
- **Client polling** of `GET /agent/runs/{id}/events` during a run. This requires the run to execute in the background (see ADR-0007).

## Reason

Streaming only helps while a run is in progress, and runs take seconds to about a minute (ADR-0007). Because the investigation runs inside the request, streaming would also require moving runs to the background first.

The timeline already shows exactly what happened, with timestamps and durations from the database. A live view would add a second delivery path to keep consistent with the stored one, with no new information.

## Tradeoffs

During a run, the user sees a busy indicator rather than individual steps.

## Consequences and when to revisit

Revisit this together with ADR-0007. If runs move to the background, add SSE that reads `agent_events` for one run after a known `event_id`. The stored events remain the single source of truth, and the stream never invents progress.
