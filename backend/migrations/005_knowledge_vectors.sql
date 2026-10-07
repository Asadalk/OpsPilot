CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_documents (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL UNIQUE,
    document TEXT NOT NULL,
    category TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(128) NOT NULL,
    UNIQUE (document_id, chunk)
);

CREATE INDEX knowledge_chunks_document_idx ON knowledge_chunks(document_id, chunk);