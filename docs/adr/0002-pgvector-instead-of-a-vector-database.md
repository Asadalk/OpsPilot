# ADR-0002: pgvector instead of a separate vector database

Status: accepted (Phase 8)

## Context

The knowledge base is small: 7 Markdown documents, split into 9 chunks. Retrieved chunks must be joined to their document and source for citations, and are stored next to agent runs.

## Decision

Store chunk vectors in PostgreSQL with the `pgvector` extension (`vector(128)`) and use exact cosine search (`ORDER BY embedding <=> query`). There is no approximate index.

## What the vectors are

The embedding is a **feature-hashed bag of words**. Each token is hashed with SHA-256 into one of 128 dimensions with a ±1 sign, then the vector is normalized (`app/rag/embeddings.py`). That makes the "vector" score a lexical similarity, not a neural semantic one.

It is deterministic, needs no model download or API call, and is good enough for the measured retrieval benchmark. Hybrid search combines it with a keyword score, because exact identifiers such as `PAY-442` and `DB_TIMEOUT` matter in operations data. Chunks with no shared term and no keyword hit are dropped.

## Alternatives considered

- **A separate vector database** (Qdrant, Pinecone, Weaviate). This would be a second store to run, secure, and keep in sync, for 9 chunks.
- **A neural embedding model** (local or hosted). Better at paraphrases, but it adds a model dependency, cost or latency, and non-determinism to tests.
- **An approximate index (HNSW or IVFFlat).** Pointless at this size, because exact search is instant.

## Reason

One database keeps citations, runs, and knowledge in the same transactions and backups. Exact search on a tiny corpus is simple and correct.

## Tradeoffs

- The hashed embeddings do not capture synonyms. "Payment latency" and "slow checkout charges" share few tokens.
- Hash collisions add a little noise.

## Consequences

- `embed_text` can be replaced by a neural model without changing the schema, except for the vector dimension.
- If the corpus grows to thousands of chunks, add an HNSW index before considering a separate store.
