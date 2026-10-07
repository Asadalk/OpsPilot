# Payment Latency Runbook

Use this runbook when payments-api latency rises above the simulator baseline. Confirm service health and request latency first. Compare the timestamp with the latest deployment and inspect database timeout logs. A database timeout is evidence of a dependency problem, not proof that the application code is defective.

For a controlled response, preserve evidence, compare the deployment version with the previous known-good version, and check database pool saturation. Recommend rollback only when deployment timing and application evidence agree. Rollback is an approved action, never an automatic command.
