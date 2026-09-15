import time

from django.core.management.base import BaseCommand

from bot.indexing import reindex_entries
from bot.ingest_url import IngestError, ingest_url
from bot.sitemap_crawler import fetch_sitemap_urls

# onmascout.de's sitemap is dominated by thousands of programmatically
# generated city x service landing pages (e.g. ads-agentur-berlin,
# ads-agentur-zuerich) — ingesting those wholesale would bloat the knowledge
# base with near-duplicate content and multiply embedding cost for no
# retrieval benefit. Default to the actual informational pages instead; pass
# --full-sitemap (with --limit) to opt into crawling everything, or use the
# admin's "Add from URL" button (Knowledge entries list) for one-off pages.
#
# /blogs/ and /lexikon/ were evaluated and deliberately excluded: /blogs/ is
# a thin index (real content lives in 78 individual articles of uneven
# quality, not the index page itself) and /lexikon/ is a ~14MB, 8.3-million-
# character generic online-marketing glossary — real content, but far too
# large and too generic (not ONMA-scout-specific) to be worth the embedding
# cost. The four biggest city pages, by contrast, checked out as genuinely
# substantive and city-specific, so they're included below.
DEFAULT_PATHS = [
    "/",
    "/ueber-uns/",
    "/leistungen/",
    "/seo-social-media/",
    "/sea-sem-agentur/",
    "/webdesign/",
    "/app-entwicklung/",
    "/online-marketing/",
    "/kontakt/",
    "/offnungszeiten/",
    "/berlin/",
    "/hamburg/",
    "/koeln/",
    "/frankfurt/",
]

CATEGORY_BY_PATH = {
    "/seo-social-media/": "SEO",
    "/sea-sem-agentur/": "SEA",
    "/webdesign/": "Webdesign",
    "/berlin/": "Standort",
    "/hamburg/": "Standort",
    "/koeln/": "Standort",
    "/frankfurt/": "Standort",
    "/app-entwicklung/": "App-Entwicklung",
}


class Command(BaseCommand):
    help = (
        "Crawl real content from onmascout.de into Knowledge entries, replacing "
        "hand-typed placeholders with the site's actual text. Defaults to a curated "
        "list of core pages — see DEFAULT_PATHS — not a full sitemap crawl."
    )

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="https://www.onmascout.de")
        parser.add_argument("--language", default="de", choices=["de", "en"])
        parser.add_argument(
            "--full-sitemap", action="store_true",
            help="Crawl every URL in the sitemap instead of the curated default list.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Cap the number of pages fetched (mainly useful with --full-sitemap).",
        )
        parser.add_argument(
            "--reindex", action="store_true",
            help="Chunk + embed created/updated entries immediately after crawling.",
        )

    def handle(self, *args, **options):
        base_url = options["base_url"].rstrip("/")
        language = options["language"]

        if options["full_sitemap"]:
            self.stdout.write("Fetching full sitemap (this returns many URLs on this site)...")
            urls = fetch_sitemap_urls(f"{base_url}/sitemap.xml")
            if options["limit"]:
                urls = urls[: options["limit"]]
        else:
            urls = [base_url + path for path in DEFAULT_PATHS]

        self.stdout.write(f"Crawling {len(urls)} page(s)...")

        created = updated = unchanged = 0
        failed = []
        changed_entries = []

        for url in urls:
            category = next((cat for path, cat in CATEGORY_BY_PATH.items() if path in url), "")
            try:
                entry, status = ingest_url(url, language, category)
            except IngestError as exc:
                failed.append((url, str(exc)))
                continue

            if status == "created":
                created += 1
                changed_entries.append(entry)
            elif status == "updated":
                updated += 1
                changed_entries.append(entry)
            else:
                unchanged += 1

            time.sleep(0.3)  # polite delay between requests

        self.stdout.write(self.style.SUCCESS(
            f"Done: {created} created, {updated} updated, {unchanged} unchanged, {len(failed)} failed."
        ))
        for url, reason in failed:
            self.stdout.write(self.style.WARNING(f"  Failed: {url} — {reason}"))

        if options["reindex"] and changed_entries:
            self.stdout.write(f"Reindexing {len(changed_entries)} changed entries...")
            total_chunks, errors = reindex_entries(changed_entries)
            self.stdout.write(self.style.SUCCESS(f"Reindexed into {total_chunks} chunks."))
            for entry, exc in errors:
                self.stdout.write(self.style.ERROR(f"  Reindex failed: {entry.title} — {exc}"))
