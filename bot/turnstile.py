"""
Cloudflare Turnstile server-side verification. Disabled entirely (every
call treated as verified) unless both TURNSTILE_SITE_KEY and
TURNSTILE_SECRET_KEY are set — same env-gated pattern as this project's
other production-only hardening (SECURE_SSL_REDIRECT, CORS lockdown, etc.):
off by default so local dev keeps working with zero config, on the moment
real keys are provided.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger("bot")

VERIFY_ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(token: str, remote_ip: str = "") -> bool:
    if not settings.TURNSTILE_ENABLED:
        return True

    if not token:
        return False

    try:
        response = requests.post(
            VERIFY_ENDPOINT,
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": remote_ip},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Turnstile verification request failed")
        return settings.TURNSTILE_FAIL_OPEN

    if not result.get("success"):
        logger.info("Turnstile verification rejected: %s", result.get("error-codes"))
        return False

    return True
