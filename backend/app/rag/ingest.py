import argparse
from pathlib import Path

from app.core.config import settings
from app.rag.embeddings import chunk_text, clean_text
from app.rag.repository import KnowledgeRepository


def ingest_directory(knowledge_dir: Path, database_url: str = settings.database_url) -> int:
    if not knowledge_dir.is_dir():
        raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")
    repository = KnowledgeRepository(database_url)
    ingested = 0
    for path in sorted(knowledge_dir.glob("**/*.md")):
        content = clean_text(path.read_text(encoding="utf-8"))
        chunks = chunk_text(content)
        if not chunks:
            continue
        source = path.relative_to(knowledge_dir).as_posix()
        document = path.stem.replace("-", " ").title()
        category = path.parent.name
        repository.replace_document(source, document, category, chunks)
        ingested += 1
    return ingested


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Ops Pilot knowledge documents into PostgreSQL.")
    parser.add_argument("--knowledge-dir", type=Path, default=Path("knowledge"))
    parser.add_argument("--database-url", default=settings.database_url)
    args = parser.parse_args()
    print(f"ingested_documents={ingest_directory(args.knowledge_dir, args.database_url)}")


if __name__ == "__main__":
    main()