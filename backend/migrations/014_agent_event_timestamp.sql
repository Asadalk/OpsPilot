ALTER TABLE agent_events
    ALTER COLUMN occurred_at SET DEFAULT clock_timestamp();
