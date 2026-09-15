from django.apps import AppConfig


class BotConfig(AppConfig):
    name = 'bot'

    def ready(self):
        from . import checks  # noqa: F401 — registers the custom checks
