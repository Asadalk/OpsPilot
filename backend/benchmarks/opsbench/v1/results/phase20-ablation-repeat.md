# OpsPilot Phase 20 — Ablation study

Deterministic component checks; no Gemini calls. These do not measure end-to-end model quality.

| Component | Scenario set | Metric | Without | With | Difference | Interpretation |
|---|---|---|---:|---:|---:|---|
| RAG | 20 — 20 fixed questions with labeled source | source_recall_at_3 | 0.0 | 1.0 | +1.0 | RAG changes the measured source retrieval rate; this does not establish diagnosis or resolution quality. |
| RAG | 20 — 20 fixed questions with labeled source | source_accuracy_at_1 | 0.0 | 0.85 | +0.85 | RAG changes the measured source retrieval rate; this does not establish diagnosis or resolution quality. |
| RAG | 20 — 20 fixed questions with labeled source | queries_returning_documents | 0 | 20 | +20 | RAG changes the measured source retrieval rate; this does not establish diagnosis or resolution quality. |
| Tool planning | 5 — 5 named services; fixed five-read-tool plan | read_tool_calls | 0 | 25 | +25 | The scripted plan adds observable read evidence at the cost of additional calls; it does not measure model tool-choice accuracy. |
| Tool planning | 5 — 5 named services; fixed five-read-tool plan | nonempty_observations | 0 | 22 | +22 | The scripted plan adds observable read evidence at the cost of additional calls; it does not measure model tool-choice accuracy. |
| Tool planning | 5 — 5 named services; fixed five-read-tool plan | evidence_dimensions_queried | 0 | 5 | +5 | The scripted plan adds observable read evidence at the cost of additional calls; it does not measure model tool-choice accuracy. |
| Incident history | 5 — same five services as the tool-plan study | history_calls | 0 | 5 | +5 | History supplies existing incident records for these services; this measures evidence availability, not causal diagnosis. |
| Incident history | 5 — same five services as the tool-plan study | incident_records_observed | 0 | 5 | +5 | History supplies existing incident records for these services; this measures evidence availability, not causal diagnosis. |
| Verification | 1 — same healthy service state with no metrics and one simulated restart | resolved_claims_without_success_verification | 1 | 0 | -1 | For this no-change fixture, execution acknowledgement alone would look successful; post-action verification returned INCONCLUSIVE and did not resolve an incident. |
| Policy engine | 6 — 6 role/action pairs in production | unsafe_writes_allowed | 5 | 0 | -5 | The fail-open control allows all six proposals; 5 violate the independent safety invariant (viewer above LOW, any CRITICAL, operator HIGH in production). With the engine, 0 do. Admin restart remains allowed by configured policy. |

## Method and limitations

- These are component-level controlled checks, not end-to-end LLM quality ablations.
- Tool planning uses a fixed scripted read plan; measured evidence retrieval is not model planning accuracy.
- Grounding and diagnosis quality are not estimated by these component checks.
- The verification comparator explicitly represents a naive mark-resolved-on-ack control.
- The no-policy comparator is fail-open (allow all writes), used to quantify the policy guard boundary.
