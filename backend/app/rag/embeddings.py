import hashlib
import math
import re

DIMENSIONS = 128
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "use", "when"}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n")).strip()


def _tokens(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_PATTERN.findall(text.lower()):
        if token in STOP_WORDS:
            continue
        if token.endswith("ies"):
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]
        tokens.append(token)
    return tokens


def chunk_text(text: str, max_words: int = 110, overlap: int = 20) -> list[str]:
    words = clean_text(text).split()
    if not words:
        return []
    chunks = []
    start = 0
    step = max(1, max_words - overlap)
    while start < len(words):
        chunks.append(" ".join(words[start : start + max_words]))
        start += step
    return chunks


def embed_text(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    tokens = _tokens(text)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"