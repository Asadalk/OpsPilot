# Deployment Rollback Runbook

A rollback is considered only after a deployment is correlated with a new error or latency signal and the prior version is known. Confirm health, metrics, logs, and deployment history before proposing it.

This document describes a recommendation procedure, not an execution authority. A human approval is required before any rollback. Capture the current version, target version, evidence timestamps, expected verification signal, and a safe stop condition.
