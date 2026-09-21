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


def _search(chunks, query_embedding: list[float], top_k: int, threshold: float):
    scored = [(cosine_similarity(query_embedding, chunk.embedding), chunk) for chunk in chunks]
    scored = [pair for pair in scored if pair[0] >= threshold]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:top_k]


def retrieve(language: str, query_embedding: list[float], top_k: int, threshold: float):
    """Returns a list of (score, KnowledgeChunk) tuples, highest score first,
    limited to `top_k` entries scoring at or above `threshold`.

    Prefers chunks in the message's own detected language (embeddings compare
    best within one language, and it keeps citations in the right language
    where same-language content exists). If that search comes up empty —
    e.g. an English question against a knowledge base that's overwhelmingly
    German — falls back to searching every language's chunks. OpenAI's
    embedding model is multilingual enough for this to work reasonably well,
    and the LLM is already instructed (BASE_INSTRUCTIONS) to reply in the
    detected language regardless of what language the retrieved context is
    in, so it translates/synthesizes rather than just parroting the context's
    original language. This means content only has to be authored once, in
    whichever language is easiest, and still answers questions in any
    supported language — at the cost of citations sometimes showing a
    source title in a different language than the reply."""
    base_qs = KnowledgeChunk.objects.filter(
        embedding__isnull=False, entry__is_active=True
    ).select_related("entry")

    same_language = _search(base_qs.filter(language=language), query_embedding, top_k, threshold)
    if same_language:
        return same_language

    return _search(base_qs, query_embedding, top_k, threshold)
