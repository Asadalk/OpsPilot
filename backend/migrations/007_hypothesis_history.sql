ALTER TABLE agent_runs
    ADD COLUMN hypothesis_history JSONB NOT NULL DEFAULT '[]'::jsonb;