ALTER TABLE agent_runs
    ADD COLUMN knowledge_citations JSONB NOT NULL DEFAULT '[]'::jsonb;