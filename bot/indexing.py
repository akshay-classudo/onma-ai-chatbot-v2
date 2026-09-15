"""Shared reindex logic used by both the admin action and the management
command — chunk a KnowledgeEntry's content, embed the chunks, replace its
KnowledgeChunk rows. Kept in one place so the two call sites can't drift."""

from .chunker import chunk_text
from .llm import LlmError, embed_texts
from .models import KnowledgeChunk


def reindex_entry(entry) -> int:
    """Returns the number of chunks written for this entry. Raises LlmError
    if the embedding call fails — callers decide how to surface that."""
    entry.chunks.all().delete()

    if not entry.retrievable or not entry.is_active:
        return 0

    pieces = chunk_text(entry.content)
    if not pieces:
        return 0

    embeddings = embed_texts(pieces)

    KnowledgeChunk.objects.bulk_create(
        [
            KnowledgeChunk(entry=entry, language=entry.language, content=piece, embedding=embedding)
            for piece, embedding in zip(pieces, embeddings)
        ]
    )
    return len(pieces)


def reindex_entries(entries):
    """Reindexes a queryset/list of entries. Returns (total_chunks, errors)
    where errors is a list of (entry, exception) pairs for entries that
    failed (e.g. embedding API quota) — other entries still get processed."""
    total_chunks = 0
    errors = []
    for entry in entries:
        try:
            total_chunks += reindex_entry(entry)
        except LlmError as exc:
            errors.append((entry, exc))
    return total_chunks, errors
