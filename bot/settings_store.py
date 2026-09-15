"""
Reads the BotSettings singleton (if an admin has configured one) with a
fall-through to the .env-backed django.conf.settings value for any field
left blank. No caching — a single indexed-PK row lookup is cheap enough to
do on every request, and skipping a cache entirely sidesteps the classic
multi-worker staleness problem (a save() in one Gunicorn worker not being
visible to the others) without needing Redis/Memcached as new infra.
"""

from .models import BotSettings


def get_bot_settings():
    """Returns the BotSettings row, or None if no admin has saved one yet —
    callers should treat None the same as "all fields blank"."""
    return BotSettings.objects.first()


def resolve(db_value, env_value):
    """First non-blank value wins: DB override, then the .env/settings.py default."""
    return db_value if db_value else env_value
