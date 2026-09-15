"""
Shared "fetch one URL, extract its content, save as a KnowledgeEntry" logic
— used by both `manage.py crawl_site` and the admin's "Add from URL" view,
so the two never drift apart.
"""

import hashlib

import requests
from django.utils import timezone

from .html_extractor import extract_page
from .models import KnowledgeEntry

USER_AGENT = "ONMAscoutBot/1.0 (+internal knowledge ingestion for onmascout.de's own chatbot)"
MIN_CONTENT_LENGTH = 150


class IngestError(Exception):
    pass


def ingest_url(url: str, language: str, category: str = "") -> tuple[KnowledgeEntry, str]:
    """Fetches `url`, extracts its content, and creates or updates the
    KnowledgeEntry for it (matched by source_url). Returns (entry, status)
    where status is "created", "updated", or "unchanged". Raises IngestError
    if the page can't be fetched or yields too little real content."""
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IngestError(f"Could not fetch {url}: {exc}") from exc

    page = extract_page(response.text)
    if len(page["content"]) < MIN_CONTENT_LENGTH:
        raise IngestError(
            f"Only {len(page['content'])} character(s) of content extracted (minimum "
            f"{MIN_CONTENT_LENGTH}) — the page may render its real content via "
            "JavaScript, which this crawler doesn't execute."
        )

    checksum = hashlib.sha256(page["content"].encode("utf-8")).hexdigest()
    title = page["title"] or url

    entry, was_created = KnowledgeEntry.objects.get_or_create(
        source_url=url,
        defaults={
            "language": language,
            "title": title,
            "content": page["content"],
            "checksum": checksum,
            "category": category,
            "last_crawled_at": timezone.now(),
        },
    )

    if was_created:
        return entry, "created"

    entry.last_crawled_at = timezone.now()
    if entry.checksum != checksum:
        entry.title = title
        entry.content = page["content"]
        entry.checksum = checksum
        if category:
            entry.category = category
        entry.save()
        return entry, "updated"

    entry.save(update_fields=["last_crawled_at"])
    return entry, "unchanged"
