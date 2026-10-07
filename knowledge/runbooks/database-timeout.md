# Database Timeout Runbook

Database timeout messages such as DB_TIMEOUT should be correlated with connection-pool metrics, request latency, and the affected service. Check whether the timeout is isolated to one service or appears across callers. ECONNRESET from a database client is a related identifier to search exactly. Recent deployment timing is useful correlation evidence but does not establish causality by itself.

Do not restart or alter a database from this runbook. Record the trace id, affected endpoint, timeout window, pool saturation evidence, and recent deployments. Escalate to the database owner when multiple services show the same dependency failure.
