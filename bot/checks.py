"""
Custom `manage.py check` rules for things Django's own `--deploy` checklist
doesn't know about (it has no idea what django-cors-headers is). Runs
automatically on every `check`/`runserver`/`migrate` etc., not just
`--deploy`, so a wide-open CORS setting surfaces immediately rather than
only when someone remembers to run the deploy checklist.
"""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_cors_not_wide_open_outside_debug(app_configs, **kwargs):
    if settings.DEBUG:
        return []

    if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
        return [
            Warning(
                "CORS_ALLOW_ALL_ORIGINS is True while DEBUG is False.",
                hint=(
                    "Set CORS_ALLOW_ALL_ORIGINS=False and list the real site "
                    "origin(s) in CORS_ALLOWED_ORIGINS before serving real traffic."
                ),
                id="bot.W001",
            )
        ]

    return []
