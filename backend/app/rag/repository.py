import psycopg
import re

from app.db.database import get_connection
from app.rag.embeddings import embed_text, vector_literal


class KnowledgeRepositoryError(Exception):
    pass


KEYWORD_PATTERN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")


def _keyword_score(query: str, content: str) -> float:
    query_tokens = set(KEYWORD_PATTERN.findall(query.lower()))
    content_tokens = set(KEYWORD_PATTERN.findall(content.lower()))
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & content_tokens) / len(query_tokens)
    phrase_bonus = 0.5 if query.strip().lower() in content.lower() else 0.0
    return min(1.0, overlap + phrase_bonus)


class KnowledgeRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def replace_document(self, source: str, document: str, category: str, chunks: list[str]) -> int:
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute(
                    "INSERT INTO knowledge_documents (source, document, category) VALUES (%s, %s, %s) "
                    "ON CONFLICT (source) DO UPDATE SET document = EXCLUDED.document, category = EXCLUDED.category, ingested_at = NOW() "
                    "RETURNING id",
                    (source, document, category),
                ).fetchone()
                document_id = row["id"]
                connection.execute("DELETE FROM knowledge_chunks WHERE document_id = %s", (document_id,))
                for index, content in enumerate(chunks, start=1):
                    connection.execute(
                        "INSERT INTO knowledge_chunks (document_id, chunk, content, embedding) VALUES (%s, %s, %s, %s::vector)",
                        (document_id, index, content, vector_literal(embed_text(content))),
                    )
            return len(chunks)
        except psycopg.Error as exc:
            raise KnowledgeRepositoryError from exc

    def _all_chunks(self) -> list[dict]:
        with get_connection(self.database_url) as connection:
            rows = connection.execute(
                "SELECT knowledge_documents.source, knowledge_documents.document, knowledge_chunks.chunk, "
                "knowledge_chunks.content, knowledge_chunks.embedding::text AS embedding "
                "FROM knowledge_chunks JOIN knowledge_documents ON knowledge_documents.id = knowledge_chunks.document_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def search_semantic(self, query: str, top_k: int = 3) -> list[dict]:
        try:
            vector = vector_literal(embed_text(query))
            with get_connection(self.database_url) as connection:
                rows = connection.execute(
                    "SELECT knowledge_documents.source, knowledge_documents.document, knowledge_chunks.chunk, "
                    "knowledge_chunks.content, ROUND((1 - (knowledge_chunks.embedding <=> %s::vector))::numeric, 6)::float8 AS similarity, "
                    "'semantic' AS retrieval_mode "
                    "FROM knowledge_chunks JOIN knowledge_documents ON knowledge_documents.id = knowledge_chunks.document_id "
                    "ORDER BY knowledge_chunks.embedding <=> %s::vector LIMIT %s",
                    (vector, vector, top_k),
                ).fetchall()
            return [dict(row) for row in rows]
        except psycopg.Error as exc:
            raise KnowledgeRepositoryError from exc

    def search_keyword(self, query: str, top_k: int = 3) -> list[dict]:
        try:
            rows = self._all_chunks()
            scored = []
            for row in rows:
                score = _keyword_score(query, row["content"])
                if score <= 0:
                    continue
                row.pop("embedding", None)
                row["similarity"] = round(score, 6)
                row["keyword_score"] = round(score, 6)
                row["retrieval_mode"] = "keyword"
                scored.append(row)
            scored.sort(key=lambda row: (-row["similarity"], row["source"], row["chunk"]))
            return scored[:top_k]
        except psycopg.Error as exc:
            raise KnowledgeRepositoryError from exc

    def search_hybrid(self, query: str, top_k: int = 3) -> list[dict]:
        candidate_limit = max(10, top_k * 3)
        semantic = self.search_semantic(query, candidate_limit)
        keyword = self.search_keyword(query, candidate_limit)
        candidates = {}
        for row in semantic:
            candidates[(row["source"], row["chunk"])] = {**row, "semantic_similarity": row["similarity"]}
        for row in keyword:
            key = (row["source"], row["chunk"])
            candidates.setdefault(key, {**row, "semantic_similarity": 0.0})
            candidates[key]["keyword_score"] = row["keyword_score"]
        for row in candidates.values():
            semantic_score = max(0.0, min(1.0, (row.get("semantic_similarity", 0.0) + 1.0) / 2.0))
            keyword_score = row.get("keyword_score", 0.0)
            row["similarity"] = round(0.45 * semantic_score + 0.55 * keyword_score, 6)
            row["retrieval_mode"] = "hybrid"
            row.pop("embedding", None)
        return sorted(candidates.values(), key=lambda row: (-row["similarity"], row["source"], row["chunk"]))[:top_k]

    def search(self, query: str, top_k: int = 3, mode: str = "hybrid") -> list[dict]:
        if mode == "semantic":
            return self.search_semantic(query, top_k)
        if mode == "keyword":
            return self.search_keyword(query, top_k)
        if mode == "hybrid":
            return self.search_hybrid(query, top_k)
        raise ValueError(f"Unknown retrieval mode: {mode}")