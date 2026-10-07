ALTER TABLE services
    ADD COLUMN current_state TEXT NOT NULL DEFAULT 'healthy'
    CHECK (current_state IN ('healthy', 'degraded', 'failed'));

INSERT INTO services (name, environment, repository, current_state) VALUES
    ('payments-api', 'production', 'github.com/opspilot/payments-api', 'degraded'),
    ('checkout-api', 'production', 'github.com/opspilot/checkout-api', 'degraded'),
    ('auth-api', 'production', 'github.com/opspilot/auth-api', 'failed'),
    ('inventory-api', 'production', 'github.com/opspilot/inventory-api', 'degraded'),
    ('notification-api', 'production', 'github.com/opspilot/notification-api', 'failed')
ON CONFLICT (name) DO UPDATE SET current_state = EXCLUDED.current_state;

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Payments latency spike', 'sev2', 'investigating', id
FROM services WHERE name = 'payments-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Payments latency spike');

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Payments latency spike - prior occurrence', 'sev3', 'resolved', id
FROM services WHERE name = 'payments-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Payments latency spike - prior occurrence');

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Checkout 500 spike', 'sev1', 'investigating', id
FROM services WHERE name = 'checkout-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Checkout 500 spike');

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Notification dependency failure', 'sev2', 'open', id
FROM services WHERE name = 'notification-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Notification dependency failure');

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Inventory failures with misleading cache evidence', 'sev2', 'investigating', id
FROM services WHERE name = 'inventory-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Inventory failures with misleading cache evidence');

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.07.14', NOW() - INTERVAL '20 minutes', 'simulator@example.com', 'success'
FROM services WHERE name = 'payments-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.07.15', NOW() - INTERVAL '12 minutes', 'simulator@example.com', 'success'
FROM services WHERE name = 'checkout-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.07.9', NOW() - INTERVAL '2 hours', 'simulator@example.com', 'success'
FROM services WHERE name = 'inventory-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '5 minutes', id, 'error', 'Database timeout acquiring payment record connection', 'trace-payments-latency-001'
FROM services WHERE name = 'payments-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '4 minutes', id, 'error', 'HTTP 500 response rate exceeded checkout threshold', 'trace-checkout-500-001'
FROM services WHERE name = 'checkout-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '3 minutes', id, 'error', 'Notification provider dependency returned connection refused', 'trace-notification-dependency-001'
FROM services WHERE name = 'notification-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '3 minutes', id, 'warn', 'Cache timeout observed; cache may be unhealthy', 'trace-inventory-misleading-001'
FROM services WHERE name = 'inventory-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '2 minutes', id, 'error', 'Token issuer unavailable; inventory requests cannot authenticate', 'trace-auth-root-cause-001'
FROM services WHERE name = 'auth-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '4 minutes', id, 'error', 'Configuration mismatch: PAYMENT_GATEWAY_URL differs from production baseline', 'trace-checkout-config-001'
FROM services WHERE name = 'checkout-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '5 minutes', id, 'http_request_latency_ms', 1842.0
FROM services WHERE name = 'payments-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '4 minutes', id, 'http_5xx_rate_percent', 18.5
FROM services WHERE name = 'checkout-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '3 minutes', id, 'dependency_error_rate_percent', 42.0
FROM services WHERE name = 'notification-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '3 minutes', id, 'request_error_rate_percent', 9.0
FROM services WHERE name = 'inventory-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '2 minutes', id, 'token_validation_error_rate_percent', 99.0
FROM services WHERE name = 'auth-api';