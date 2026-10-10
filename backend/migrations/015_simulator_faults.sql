-- Hidden ground truth for the simulator. Read APIs and agent tools never select this
-- column; executed actions use it so only the action that matches the fault heals it.
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS fault TEXT
    CHECK (fault IN ('connection_pool_exhaustion', 'process_crash', 'bad_deployment',
                     'upstream_dependency', 'external_dependency'));

UPDATE services SET fault = 'connection_pool_exhaustion' WHERE name = 'payments-api' AND current_state <> 'healthy';
UPDATE services SET fault = 'bad_deployment' WHERE name = 'checkout-api' AND current_state <> 'healthy';
UPDATE services SET fault = 'process_crash' WHERE name = 'auth-api' AND current_state <> 'healthy';
UPDATE services SET fault = 'upstream_dependency' WHERE name = 'inventory-api' AND current_state <> 'healthy';
UPDATE services SET fault = 'external_dependency' WHERE name = 'notification-api' AND current_state <> 'healthy';

-- Earlier known-good releases make rollback a real option (and a real wrong option for payments).
INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.06.11', NOW() - INTERVAL '1 day', 'simulator@example.com', 'success'
FROM services WHERE name = 'checkout-api'
ON CONFLICT (service_id, version) DO NOTHING;

INSERT INTO deployments (service_id, version, deployed_at, author, status)
SELECT id, '2026.10.06.9', NOW() - INTERVAL '1 day', 'simulator@example.com', 'success'
FROM services WHERE name = 'payments-api'
ON CONFLICT (service_id, version) DO NOTHING;
