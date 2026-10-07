ALTER TABLE actions ADD COLUMN idempotency_key TEXT;

UPDATE actions
SET idempotency_key = run_id::text || ':' || lower(btrim(proposal->>'action_type')) || ':' || lower(btrim(proposal->>'target'));

ALTER TABLE actions ALTER COLUMN idempotency_key SET NOT NULL;
CREATE UNIQUE INDEX actions_idempotency_key_unique ON actions(idempotency_key);
