"""
Answer caching: skip both the embedding call and the LLM call on a repeated
question. Keyed on (language, normalized question text) — shared across
every session, not scoped to one conversation. This intentionally ignores
conversation history: a cache hit answers the question in isolation, the
same way an FAQ would. That's the right tradeoff for exact/near-exact
repeats of common questions ("what does SEO cost?"); a question that only
makes sense in context of the preceding turns won't normalize to the same
key as anyone else's, so it naturally falls through to a real LLM call.
"""

import hashlib
import re
from datetime import timedelta

from django.utils import timezone

from .models import AnswerCache

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[?!.\s]+$")


def normalize_question(text: str) -> str:
    text = text.strip().lower()
    text = _TRAILING_PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def _hash_key(language: str, normalized: str) -> str:
    return hashlib.sha256(f"{language}:{normalized}".encode("utf-8")).hexdigest()


def get_cached_answer(language: str, message: str):
    """Returns the AnswerCache row on a live (non-expired) hit, else None.
    Bumps hit_count on a hit."""
    normalized = normalize_question(message)
    if not normalized:
        return None

    entry = AnswerCache.objects.filter(
        question_hash=_hash_key(language, normalized), expires_at__gt=timezone.now()
    ).first()

    if entry is not None:
        entry.hit_count += 1
        entry.save(update_fields=["hit_count"])

    return entry


def store_answer(language: str, message: str, answer: str, sources: list | None, ttl_seconds: int) -> None:
    normalized = normalize_question(message)
    if not normalized:
        return

    AnswerCache.objects.update_or_create(
        question_hash=_hash_key(language, normalized),
        defaults={
            "language": language,
            "question_text": normalized,
            "answer": answer,
            "sources_json": sources,
            "expires_at": timezone.now() + timedelta(seconds=ttl_seconds),
        },
    )
