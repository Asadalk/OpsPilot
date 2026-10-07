# Example operational guidelines

These guidelines are illustrative demo context for Ops Assistant. Adapt them to the organization before using them for real operational decisions.

High-priority production incidents affecting customers should be escalated immediately, assigned an incident owner, and tracked until customer impact is resolved.

Security incidents, including credentials exposed in a public repository, must be assigned to the security team and handled through the organization's incident response process.

Customer-impacting outages should receive a status update within the organization's defined communications period, with the next update time recorded.

Production database migrations require a rollback plan, a migration owner, and verification that the rollback procedure is usable before execution.

Production deployments require post-deployment verification, including health checks and a confirmation that customer-facing behavior is working as expected.
