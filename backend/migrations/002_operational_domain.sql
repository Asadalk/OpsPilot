CREATE TABLE services (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL CHECK (environment IN ('development', 'staging', 'production')),
    repository TEXT NOT NULL
);

CREATE TABLE incidents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('sev1', 'sev2', 'sev3', 'sev4')),
    status TEXT NOT NULL CHECK (status IN ('open', 'investigating', 'resolved')),
    service_id BIGINT NOT NULL REFERENCES services(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE deployments (
    deployment_id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL REFERENCES services(id),
    version TEXT NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'rolled_back')),
    UNIQUE (service_id, version)
);

CREATE TABLE logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    service_id BIGINT NOT NULL REFERENCES services(id),
    level TEXT NOT NULL CHECK (level IN ('debug', 'info', 'warn', 'error')),
    message TEXT NOT NULL,
    trace_id TEXT NOT NULL
);

CREATE TABLE metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    service_id BIGINT NOT NULL REFERENCES services(id),
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL
);

CREATE INDEX incidents_service_status_idx ON incidents(service_id, status);
CREATE INDEX deployments_service_deployed_at_idx ON deployments(service_id, deployed_at DESC);
CREATE INDEX logs_service_timestamp_idx ON logs(service_id, timestamp DESC);
CREATE INDEX metrics_service_timestamp_idx ON metrics(service_id, timestamp DESC);

INSERT INTO services (name, environment, repository) VALUES
    ('orders-api', 'production', 'github.com/opspilot/orders-api'),
    ('payments-worker', 'production', 'github.com/opspilot/payments-worker'),
    ('catalog-api', 'staging', 'github.com/opspilot/catalog-api')
ON CONFLICT (name) DO NOTHING;

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Elevated order latency', 'sev2', 'investigating', id
FROM services WHERE name = 'orders-api'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Elevated order latency');

INSERT INTO incidents (title, severity, status, service_id)
SELECT 'Payment queue backlog', 'sev3', 'open', id
FROM services WHERE name = 'payments-worker'
  AND NOT EXISTS (SELECT 1 FROM incidents WHERE title = 'Payment queue backlog');

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.07.1', NOW() - INTERVAL '2 hours', 'maya@example.com', 'success'
FROM services WHERE name = 'orders-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.06.3', NOW() - INTERVAL '1 day', 'noah@example.com', 'success'
FROM services WHERE name = 'payments-worker'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.07.2', NOW() - INTERVAL '30 minutes', 'maya@example.com', 'failed'
FROM services WHERE name = 'catalog-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '10 minutes', id, 'error', 'Database pool exhausted while creating order', 'trace-orders-001'
FROM services WHERE name = 'orders-api';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '8 minutes', id, 'warn', 'Retry queue depth exceeded warning threshold', 'trace-payments-001'
FROM services WHERE name = 'payments-worker';

INSERT INTO logs (timestamp, service_id, level, message, trace_id)
SELECT NOW() - INTERVAL '5 minutes', id, 'info', 'Catalog deployment health check started', 'trace-catalog-001'
FROM services WHERE name = 'catalog-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '10 minutes', id, 'http_request_latency_ms', 842.5
FROM services WHERE name = 'orders-api';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '8 minutes', id, 'queue_depth', 127
FROM services WHERE name = 'payments-worker';

INSERT INTO metrics (timestamp, service_id, metric_name, value)
SELECT NOW() - INTERVAL '5 minutes', id, 'http_5xx_rate', 0.04
FROM services WHERE name = 'catalog-api';