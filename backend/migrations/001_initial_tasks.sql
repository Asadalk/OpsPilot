CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    owner TEXT NOT NULL,
    deadline TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    status TEXT NOT NULL CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at TEXT NOT NULL
)