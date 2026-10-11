# Security

This page is a summary. The threat model, with the enforcement point and test for each threat, is in [threat-model.md](threat-model.md). How to run the project safely is in [SECURITY.md](../SECURITY.md).

| Control | Where | Proven by |
|---|---|---|
| Model can only read | `OpsAgent` refuses tools that are unknown or not READ; the Groq schema limits tool names | `tests/security/test_tool_injection.py`, `tests/test_groq.py` |
| Untrusted content framing | `build_decision_prompt` | `tests/security/test_prompt_injection.py` |
| Server-side risk and policy | `app/policy/engine.py` | `tests/test_policy.py` |
| Customer scope | `app/core/customer.py`, the tools, the policy engine | `tests/test_customer.py` |
| Human approval and separation of duties | `app/approval/` | `tests/test_approval.py`, `tests/security/test_authorization_and_execution.py` |
| Verification against ground truth | `app/db/simulator_actions.py` | `tests/test_approval.py`, `tests/test_opsbench.py` |
| Append-only records | migrations 011 and 013 (triggers) | `tests/test_agent_events.py` |
| No default credentials outside development | `check_deployment_settings` | `tests/test_auth.py` |
| Secrets stay on the backend | `backend/.env` (gitignored); keys never enter prompts | `tests/security/test_prompt_injection.py` |

The OpsBench `prompt_injection`, `permission_violation`, `dangerous_request`, and `approval_rejection` categories measure these controls end to end with a live model (see [evaluation.md](evaluation.md)).
