# Retrieval

## Ingestion

The source documents are Markdown files under `knowledge/`: runbooks, postmortems, and architecture notes. Ingestion runs at backend startup when `KNOWLEDGE_DIR` is set (Compose mounts `./knowledge` at `/knowledge`), or by hand with `python -m app.rag.ingest --knowledge-dir knowledge`.

Each document is processed in four steps:
1. **Clean:** collapse whitespace.
2. **Chunk:** about 110 words per chunk, with a 20-word overlap.
3. **Embed:** a hashed bag-of-words vector.
4. **Store:** in `knowledge_documents` and `knowledge_chunks`.

Re-ingesting a source replaces its chunks. A missing directory stops startup, so retrieval is never empty without anyone noticing.

## Vectors

`embed_text` (`app/rag/embeddings.py`) works like this:
- It lowercases the text, tokenizes it, drops stop words, and applies light plural stemming.
- It hashes each token with SHA-256 into one of 128 dimensions, with a ±1 sign.
- It normalizes the result.

The resulting cosine similarity is **lexical**: it rewards shared terms, not shared meaning. That choice is deliberate. It is deterministic, needs no model, and is enough for the measured benchmark (see ADR-0002).

## Search modes

| Mode | Score |
|---|---|
| `semantic` | cosine similarity of the hashed vectors (pgvector `<=>`, exact search) |
| `keyword` | share of query tokens found in the chunk, plus 0.5 if the whole query appears verbatim |
| `hybrid` (default) | 0.45 × vector score (cosine rescaled to 0–1) + 0.55 × keyword score, over 10 candidates from each mode |

In hybrid mode, a chunk with no shared term (cosine ≤ 0) and no keyword hit is dropped. Without that filter, every chunk scored at least 0.225, so even a nonsense query returned three "matches".

Exact identifiers such as `PAY-442`, `v3.8.2`, `DB_TIMEOUT`, and `ECONNRESET` are why the keyword score carries the larger weight.

## How the agent uses retrieval

- It retrieves once per run, top 3, using the request text.
- The prompt receives excerpts of at most 300 characters each, marked as untrusted data.
- The diagnosis gets a `Sources:` list. Note that this lists every retrieved source, not only the ones the model relied on.
- A retrieval failure is recorded as uncertainty and blocks action proposals. An empty result is a warning only, and it never means "no relevant guidance exists".

## Measurement

Phase 9 compared the three modes on labeled questions, and hybrid was chosen. In the deterministic component study, removing RAG drops source recall@3 from 20/20 to 0/20 on the labeled set. Live agent results with and without RAG are in [evaluation.md](evaluation.md).
