ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_status_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_status_check CHECK (status IN ('investigating', 'paused', 'completed', 'failed'));

CREATE TABLE actions (
    action_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    proposal JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending_approval', 'approved', 'rejected', 'expired', 'executed')),
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMPTZ
);

CREATE TABLE approvals (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    action_id UUID NOT NULL UNIQUE REFERENCES actions(action_id) ON DELETE CASCADE,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    decision TEXT NOT NULL CHECK (decision IN ('pending', 'approved', 'rejected', 'expired')),
    decided_by TEXT,
    reason TEXT
);

CREATE INDEX approvals_pending_idx ON approvals(decision, expires_at);
