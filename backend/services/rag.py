"""Lightweight lexical retrieval over the example operational guidelines."""
from dataclasses import dataclass
from math import log
from pathlib import Path
import re

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "team",
}
GUIDELINES_DIR = Path(__file__).resolve().parents[1] / "guidelines"


@dataclass(frozen=True)
class GuidelineChunk:
    source: str
    chunk_id: str
    text: str
    score: float = 0.0


def _tokens(text: str) -> set[str]:
    tokens = {token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS}
    normalized: set[str] = set()
    for token in tokens:
        if token in {"deploy", "deployed", "deployment", "deployments"}:
            normalized.add("deploy")
        elif token.endswith("ies"):
            normalized.add(token[:-3] + "y")
        elif token.endswith("s") and len(token) > 4:
            normalized.add(token[:-1])
        else:
            normalized.add(token)
    return normalized


def load_guideline_chunks(directory: Path = GUIDELINES_DIR) -> list[GuidelineChunk]:
    chunks: list[GuidelineChunk] = []
    for path in sorted(directory.glob("*.md")):
        paragraphs = [part.strip() for part in path.read_text(encoding="utf-8").split("\n\n")]
        for index, paragraph in enumerate(paragraphs, start=1):
            if paragraph and not paragraph.startswith("#"):
                chunks.append(GuidelineChunk(path.name, f"{path.stem}-{index}", paragraph))
    return chunks


def retrieve(query: str, top_k: int = 3, directory: Path = GUIDELINES_DIR) -> list[GuidelineChunk]:
    """Return the highest-scoring guideline chunks using IDF-weighted token overlap."""
    query_tokens = _tokens(query)
    chunks = load_guideline_chunks(directory)
    if not query_tokens or not chunks:
        return []

    document_tokens = [_tokens(chunk.text) for chunk in chunks]
    document_frequency = {
        token: sum(token in tokens for tokens in document_tokens) for token in query_tokens
    }
    scored: list[GuidelineChunk] = []
    for chunk, tokens in zip(chunks, document_tokens):
        overlap = query_tokens & tokens
        score = sum(log((1 + len(chunks)) / (1 + document_frequency[token])) for token in overlap)
        if score >= 0.5 and len(overlap) >= 2:
            scored.append(GuidelineChunk(chunk.source, chunk.chunk_id, chunk.text, round(score, 4)))
    scored.sort(key=lambda chunk: (-chunk.score, chunk.source, chunk.chunk_id))
    return scored[:top_k]


def build_context(chunks: list[GuidelineChunk]) -> str:
    if not chunks:
        return "No matching operational guidelines were retrieved."
    return "\n".join(
        f"[{chunk.source}::{chunk.chunk_id}; relevance={chunk.score}] {chunk.text}"
        for chunk in chunks
    )
