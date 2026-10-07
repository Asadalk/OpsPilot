import psycopg

from app.db.database import get_connection
from app.rag.embeddings import embed_text, vector_literal


class KnowledgeRepositoryError(Exception):
    pass


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

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        try:
            vector = vector_literal(embed_text(query))
            with get_connection(self.database_url) as connection:
                rows = connection.execute(
                    "SELECT knowledge_documents.source, knowledge_documents.document, knowledge_chunks.chunk, "
                    "knowledge_chunks.content, ROUND((1 - (knowledge_chunks.embedding <=> %s::vector))::numeric, 6)::float8 AS similarity "
                    "FROM knowledge_chunks JOIN knowledge_documents ON knowledge_documents.id = knowledge_chunks.document_id "
                    "ORDER BY knowledge_chunks.embedding <=> %s::vector LIMIT %s",
                    (vector, vector, top_k),
                ).fetchall()
            return [dict(row) for row in rows]
        except psycopg.Error as exc:
            raise KnowledgeRepositoryError from exc