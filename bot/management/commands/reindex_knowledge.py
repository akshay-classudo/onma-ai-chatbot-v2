from django.core.management.base import BaseCommand

from bot.indexing import reindex_entries
from bot.models import KnowledgeEntry


class Command(BaseCommand):
    help = "Chunk + embed all active, retrievable knowledge entries into KnowledgeChunk rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--language", choices=["de", "en"], help="Only reindex entries in this language."
        )

    def handle(self, *args, **options):
        entries = KnowledgeEntry.objects.filter(is_active=True, retrievable=True)
        if options["language"]:
            entries = entries.filter(language=options["language"])

        if not entries.exists():
            self.stdout.write(self.style.WARNING("No active, retrievable knowledge entries found."))
            return

        total_chunks, errors = reindex_entries(entries)

        self.stdout.write(
            self.style.SUCCESS(f"Reindexed {entries.count()} entries into {total_chunks} chunks.")
        )
        for entry, exc in errors:
            self.stdout.write(self.style.ERROR(f"  Failed: [{entry.language}] {entry.title} — {exc}"))
