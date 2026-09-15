"""Brute-force cosine-similarity search over KnowledgeChunk embeddings.

The V2 build guide specs pgvector for this. At this corpus size (a handful
of knowledge entries, not a crawled site) a full scan in Python is fast
enough and avoids requiring a PostgreSQL install just for the foundation
pass — swap this module for a pgvector query later if the corpus grows.
"""

import math

from .models import KnowledgeChunk


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(language: str, query_embedding: list[float], top_k: int, threshold: float):
    """Returns a list of (score, KnowledgeChunk) tuples, highest score first,
    limited to `top_k` entries scoring at or above `threshold`."""
    chunks = KnowledgeChunk.objects.filter(
        language=language, embedding__isnull=False, entry__is_active=True
    ).select_related("entry")

    scored = [(cosine_similarity(query_embedding, chunk.embedding), chunk) for chunk in chunks]
    scored = [pair for pair in scored if pair[0] >= threshold]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return scored[:top_k]
