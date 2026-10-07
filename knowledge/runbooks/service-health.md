# Service Health Runbook

Start an investigation with the service health state. Healthy means the simulator reports normal operation, degraded means an observable signal is impaired, and failed means the service is unavailable or unable to satisfy its dependency contract.

Health is a summary, not a diagnosis. Always pair health with metrics, logs, recent deployments, and incident history. A degraded service can have a healthy dependency, and a healthy service can depend on a failed upstream service.
