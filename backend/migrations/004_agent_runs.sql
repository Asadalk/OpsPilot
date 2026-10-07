CREATE TABLE agent_runs (
    run_id UUID PRIMARY KEY,
    user_request TEXT NOT NULL,
    service TEXT,
    severity TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    hypotheses JSONB NOT NULL DEFAULT '[]'::jsonb,
    diagnosis TEXT,
    proposed_action TEXT,
    status TEXT NOT NULL CHECK (status IN ('investigating', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE agent_tool_calls (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    call_index INTEGER NOT NULL,
    tool TEXT NOT NULL,
    arguments JSONB NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    result JSONB,
    success BOOLEAN NOT NULL,
    error TEXT,
    UNIQUE (run_id, call_index)
);

CREATE INDEX agent_tool_calls_run_idx ON agent_tool_calls(run_id, call_index);