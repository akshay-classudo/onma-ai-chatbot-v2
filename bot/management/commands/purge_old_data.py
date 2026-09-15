from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from bot.models import AnswerCache, ChatSession


class Command(BaseCommand):
    help = (
        "GDPR retention: delete chat sessions (and their messages, via cascade) "
        "older than RETENTION_DAYS. Leads are untouched — separate retention basis. "
        "Also sweeps expired AnswerCache rows (disk hygiene, not a privacy requirement — "
        "the cache is unlinked from any session and expiry already governs correctness)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=None,
            help="Override RETENTION_DAYS from settings/.env for this run.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report how many rows would be deleted, without deleting them.",
        )

    def handle(self, *args, **options):
        days = options["days"] if options["days"] is not None else settings.RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        sessions = ChatSession.objects.filter(created_at__lt=cutoff)
        expired_cache = AnswerCache.objects.filter(expires_at__lt=timezone.now())

        session_count = sessions.count()
        cache_count = expired_cache.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Would delete {session_count} session(s) older than {days} days, "
                f"and {cache_count} expired answer-cache row(s) (dry run)."
            )
            return

        sessions.delete()
        expired_cache.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Deleted {session_count} session(s) older than {days} days "
            f"and {cache_count} expired answer-cache row(s)."
        ))
