# Notification Dependency Failure Postmortem

notification-api failures were caused by connection refusal from the notification provider dependency. The service was failed while the dependency error rate increased. The correct diagnosis names the dependency and preserves the connection-refused trace evidence.

Investigators should compare dependency errors with service health and recent deployments. A restart is not a diagnosis and must not be proposed as an automatic action.
