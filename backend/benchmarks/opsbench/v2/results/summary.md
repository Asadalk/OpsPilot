OpsBench 2.0.0 · dataset SHA-256 `92ae793b1d50…`

| Run | System | Scenarios | Task success | Action | Diagnosis | Grounded | Tool recall | Arguments | Efficiency | Safety | Median s | Tokens/scenario |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| groq-full | baseline | 100 | 24% (n=100) | 34% (n=100) | 3% (n=100) | 0% (n=92) | 0% (n=100) | — | — | 26% (n=100) | 0.394 | 333 |
| groq-full | opspilot | 100 | 69% (n=100) | 70% (n=100) | 69% (n=100) | 67% (n=92) | 80% (n=100) | 98% (n=99) | 93% (n=99) | 86% (n=100) | 16.718 | 11647 |
| groq-repeat | opspilot | 100 | 71% (n=100) | 72% (n=100) | 72% (n=100) | 71% (n=92) | 80% (n=100) | 98% (n=99) | 94% (n=99) | 86% (n=100) | 7.78 | 11187 |
| groq-ablation | opspilot − history | 100 | 73% (n=100) | 73% (n=100) | 65% (n=100) | 64% (n=92) | 76% (n=100) | 97% (n=98) | 90% (n=98) | 89% (n=100) | 9.422 | 11074 |
| groq-ablation | opspilot − planning | 100 | 81% (n=100) | 81% (n=100) | 96% (n=100) | 78% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 97% (n=100) | 2.301 | 2722 |
| groq-ablation | opspilot − rag | 100 | 68% (n=100) | 70% (n=100) | 44% (n=100) | 64% (n=92) | 70% (n=100) | 92% (n=99) | 90% (n=99) | 86% (n=100) | 6.857 | 8738 |
| groq-ablation | opspilot − verification | 100 | 67% (n=100) | 67% (n=100) | 63% (n=100) | 68% (n=92) | 78% (n=100) | 98% (n=98) | 94% (n=98) | 83% (n=100) | 7.649 | 11009 |
| rule-run-1 | rule | 100 | 98% (n=100) | 98% (n=100) | 96% (n=100) | 0% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 0.538 | — |
| ablation-rule | obedient − verification | 100 | 98% (n=100) | 98% (n=100) | 89% (n=100) | 0% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 94% (n=100) | 0.562 | — |
| ablation-rule | obedient | 100 | 98% (n=100) | 98% (n=100) | 89% (n=100) | 0% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 0.541 | — |
| ablation-rule | rule − policy | 100 | 82% (n=100) | 98% (n=100) | 96% (n=100) | 0% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 84% (n=100) | 0.52 | — |
| ablation-rule | rule | 100 | 98% (n=100) | 98% (n=100) | 96% (n=100) | 0% (n=92) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 100% (n=100) | 0.49 | — |

Task success by category:

| Run | System | ambiguous_incident | approval_rejection | dangerous_request | misleading_evidence | missing_information | multi_step_incident | permission_violation | prompt_injection | retrieval_failure | simple_incident | tool_failure | verification_failure |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| groq-full | baseline | 0/8 | 0/8 | 2/8 | 0/8 | 7/8 | 2/8 | 0/8 | 0/8 | 0/8 | 5/12 | 0/8 | 8/8 |
| groq-full | opspilot | 3/8 | 5/8 | 5/8 | 0/8 | 8/8 | 7/8 | 6/8 | 4/8 | 8/8 | 9/12 | 7/8 | 7/8 |
| groq-repeat | opspilot | 4/8 | 7/8 | 6/8 | 0/8 | 8/8 | 6/8 | 6/8 | 4/8 | 8/8 | 8/12 | 6/8 | 8/8 |
| groq-ablation | opspilot − history | 3/8 | 5/8 | 6/8 | 0/8 | 8/8 | 7/8 | 7/8 | 4/8 | 8/8 | 9/12 | 8/8 | 8/8 |
| groq-ablation | opspilot − planning | 5/8 | 8/8 | 8/8 | 0/8 | 7/8 | 5/8 | 8/8 | 7/8 | 8/8 | 12/12 | 8/8 | 5/8 |
| groq-ablation | opspilot − rag | 1/8 | 7/8 | 5/8 | 1/8 | 7/8 | 6/8 | 7/8 | 5/8 | 8/8 | 7/12 | 6/8 | 8/8 |
| groq-ablation | opspilot − verification | 1/8 | 4/8 | 6/8 | 0/8 | 8/8 | 5/8 | 7/8 | 4/8 | 8/8 | 8/12 | 8/8 | 8/8 |
| rule-run-1 | rule | 6/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 12/12 | 8/8 | 8/8 |
| ablation-rule | obedient − verification | 6/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 12/12 | 8/8 | 8/8 |
| ablation-rule | obedient | 6/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 12/12 | 8/8 | 8/8 |
| ablation-rule | rule − policy | 6/8 | 0/8 | 8/8 | 8/8 | 8/8 | 8/8 | 0/8 | 8/8 | 8/8 | 12/12 | 8/8 | 8/8 |
| ablation-rule | rule | 6/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 12/12 | 8/8 | 8/8 |
