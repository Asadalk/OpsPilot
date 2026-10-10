-- Who asked for the action, so the requester cannot also approve it (separation of duties).
ALTER TABLE approvals ADD COLUMN IF NOT EXISTS requested_by TEXT;
