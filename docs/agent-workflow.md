# Agent workflow

The agent is `OpsAgent.investigate` in `backend/app/agent/agent.py`. It is one loop of at most 8 steps, and every step is recorded.

```text
create run (agent_runs, run.started)
  │
  ├─ retrieve knowledge once (hybrid search, top 3) ─────────── event: retrieval
  │
  └─ for step in 1..8:
       ask the provider for one decision ────────────────────── event: classify / planning / diagnosis
         (prompt = request + evidence + knowledge excerpts + READ tools, all marked untrusted)
       │
       ├─ call_tool  → refuse if the tool is unknown or not READ (run fails, nothing runs)
       │              → run the tool with a timeout; one retry if the failure is transient
       │              → record the call (agent_tool_calls + event) and add the result as evidence
       │
       └─ diagnose   → add citations; check evidence completeness
                     → incomplete evidence (failed tool, no data, retrieval down)?
                          withhold any proposal, mark escalation, run = failed
                     → proposal? policy engine: allow / deny / require_approval ── event: policy
                          require_approval → pending approval, run = paused
                          allow (restart or rollback) → executed as policy:<user>
                          deny → recorded, nothing runs
                     → run = completed or paused ─────────────────────────────── event: run.completed

step limit reached → run = failed (step_limit)
```

## The decision contract

Every provider returns an `AgentDecision`:

- `action`: `call_tool` or `diagnose`.
- `tool_name` and `arguments`: required for `call_tool`. The tool must be one of the advertised READ tools.
- `diagnosis`: required for `diagnose`.
- `hypotheses`: the competing explanations. Each has a model-assigned score in [0, 1] (not a calibrated probability) and supporting or contradicting evidence.
- `proposed_action`: optional. One action type, a target, a reason, and evidence. Any risk level the model includes is ignored.

Invalid output becomes a `malformed_model_response` failure, and the run fails. The system never guesses at what the model meant.

## Providers

`build_decision_provider()` is the only place that picks a provider; `agent.py` does not reference any of them.

| `LLM_PROVIDER` | Class | Use |
|---|---|---|
| `groq` (default) | `GroqDecisionProvider` | Groq HTTP API with a JSON-schema response and token pacing |
| `gemini` | `GeminiDecisionProvider` | Google GenAI SDK |
| `mock` | `MockDecisionProvider` | Offline and deterministic, with failure modes (`MOCK_LLM_MODE`) |

## Failure handling inside the loop

| Failure | Behavior |
|---|---|
| Model timeout, connection error, HTTP 429 or 5xx | One retry with backoff (honoring `retry-after`, capped at 30 s), then the run fails with the reason recorded |
| Malformed model output | No retry; the run fails with `malformed_model_response` and the invalid fields |
| Tool timeout or transient database error | One retry |
| Tool fails permanently | Recorded as a failed observation; the model may try other tools; the final diagnosis is marked uncertain and any proposal is withheld |
| Tool returns empty data | Warning added: "no data is not evidence of health" |
| Retrieval fails or is empty | Uncertainty recorded; a retrieval failure blocks proposals, an empty result does not |

## After the loop

Approvals and execution happen outside the agent, in `ApprovalService` (`app/approval`):
1. Approve or reject; the requester cannot decide their own action.
2. Execute the simulator action (`app/db/simulator_actions.py`).
3. Verify. If verification fails, re-read the evidence and retry once, then escalate.
4. Resolve incidents only on `SUCCESS`.
5. Append the outcome to the run's diagnosis.
