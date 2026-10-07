CREATE TABLE agent_events (
    event_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runs(run_id),
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    model TEXT,
    tool TEXT,
    status TEXT NOT NULL,
    error TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX agent_events_run_order_idx ON agent_events(run_id, occurred_at, event_id);
CREATE INDEX agent_events_type_idx ON agent_events(event_type, occurred_at);

CREATE FUNCTION reject_agent_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'agent_events are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_events_no_update_or_delete
    BEFORE UPDATE OR DELETE ON agent_events
    FOR EACH ROW EXECUTE FUNCTION reject_agent_event_mutation();

CREATE FUNCTION reject_agent_event_truncate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'agent_events cannot be truncated';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_events_no_truncate
    BEFORE TRUNCATE ON agent_events
    FOR EACH STATEMENT EXECUTE FUNCTION reject_agent_event_truncate();

REVOKE UPDATE, DELETE, TRUNCATE ON agent_events FROM PUBLIC;
