# ADR-0007: Run investigations synchronously (no job queue in v1)

Status: accepted

## Context

`POST /agent/investigate` runs the whole agent loop inside the HTTP request. The loop ends when the run pauses for approval or finishes.

A background queue (for example Redis plus a worker) is the usual answer when requests are too long to hold open. We measured actual run times before deciding. These are live OpsBench runs on Groq `openai/gpt-oss-120b`. Each figure covers the investigation plus the approval decision and the simulated execution.

| Run | Scenarios | Median | p95 | Max |
|---|---|---|---|---|
| Full run | 30 (sampled during the run) | 21 s | 35 s | 39 s |
| Repeat run | 33 (sampled during the run) | 6 s | 50 s | 56 s |

One step is bounded by its timeout of 25 s, plus up to 61 s of rate-limit pacing. A run is bounded by at most 8 steps.

## Decision

Keep investigations synchronous. Do not add Redis, a worker process, or job-state tables in v1.

## Alternatives considered

- **Redis queue plus one worker:** `POST /runs` returns a job id, and a worker executes it. The client polls the job state.
- **FastAPI `BackgroundTasks`:** runs after the response is sent, in the same process.
- **A PostgreSQL-backed job table:** the database is already present.

## Reason

Runs finish within about a minute, well inside normal HTTP and browser timeouts. The run is persisted step by step in `agent_events`, so a dropped connection loses no record. The run's state can be read with `GET /agent/runs/{id}/events`.

A queue would add a broker, a second process, retry semantics, and job-state handling, and none of it solves a problem we have.

## Tradeoffs

- The browser waits during an investigation (the UI shows a busy state).
- A client disconnect does not cancel the run cleanly. The run still completes and is stored.
- Throughput is limited to the API workers. That is fine for a single-team tool and a simulator.

## Consequences and when to revisit

Revisit this if runs regularly exceed about 2 minutes, if many investigations run at once, or if runs must outlive a backend restart. The likely first step is a job table in PostgreSQL with a single worker. Redis only becomes worth it if the database-backed queue becomes a measured bottleneck.
