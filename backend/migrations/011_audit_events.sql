CREATE TABLE audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    run_id UUID,
    reason TEXT,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_events_entity_idx ON audit_events(entity_type, entity_id, occurred_at, event_id);
CREATE INDEX audit_events_run_idx ON audit_events(run_id, occurred_at, event_id);
CREATE INDEX audit_events_type_idx ON audit_events(event_type, occurred_at);

CREATE FUNCTION reject_audit_event_row_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_or_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_event_row_mutation();

CREATE FUNCTION reject_audit_event_truncate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events cannot be truncated';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_event_truncate();

REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM PUBLIC;

INSERT INTO audit_events (actor, event_type, entity_type, entity_id, reason, result, details)
SELECT
    'simulator-seed',
    'incident.created',
    'incident',
    incidents.id::TEXT,
    'Seeded controlled simulator incident.',
    jsonb_build_object('status', 'created'),
    jsonb_build_object('title', incidents.title, 'severity', incidents.severity, 'service', services.name, 'status', incidents.status)
FROM incidents
JOIN services ON services.id = incidents.service_id;
