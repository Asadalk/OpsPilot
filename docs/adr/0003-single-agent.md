# ADR-0003: One agent with a manual loop

Status: accepted (Phase 7)

## Context

Agent frameworks often split work across a planner, researcher, diagnoser, executor, and critic. OpsPilot's task is one investigation per incident: gather evidence, diagnose, and propose one action.

## Decision

Use a single agent (`OpsAgent.investigate`) with a hand-written loop of at most 8 steps. On each step, the model either selects one registered READ tool or returns a diagnosis. The application runs the tool and records the result. No orchestration framework is used.

## Alternatives considered

- **A multi-agent pipeline** (planner, investigator, critic, executor).
- **A graph framework** such as LangGraph, or a framework's built-in agent executor.

## Reason

Every decision, tool call, and failure is one row in `agent_events`, so a run can be read top to bottom. Splitting into agents would add hand-offs, context to pass between agents, more model calls, and more failure points.

Multiple agents would need measured value to justify that complexity, and the OpsBench measurements (docs/evaluation.md, 100 scenarios per configuration) point the other way:

- **The safety-critical work is deterministic.**
  - Removing verification let the live agent close 17 incidents that were still broken.
  - Removing the policy engine let 16 actions run for viewers or after rejections.

  No amount of extra model reasoning replaces those checks.
- **Less model autonomy did better, not more.** A fixed evidence sequence, with the model only diagnosing, beat model-chosen tool calls on the same model:
  - task success 81% vs 68%;
  - safety 97% vs 86%;
  - about 4× fewer tokens.
- **The remaining failures are reasoning errors inside one investigation** (misleading evidence: 0/8). These are better addressed by better evidence gathering, such as following upstream errors, than by adding agents to the conversation.

## Tradeoffs

- One prompt carries all the context, so prompt size grows with the evidence collected (kept compact; see the provider notes).
- There is no separate critic pass. A wrong diagnosis is caught downstream by policy, the human reviewer, and verification, not by a second model.

## Consequences

- Testing is straightforward: scripted providers drive the real loop, and a mock provider exercises the failure paths.
- If a future experiment shows that a critic pass measurably improves diagnosis accuracy on OpsBench, add it as one more step in this loop, not as a new orchestration layer.
