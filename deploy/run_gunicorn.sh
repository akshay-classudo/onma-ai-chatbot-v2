#!/bin/sh
# Production entrypoint for Linux — Gunicorn. Put Nginx in front for TLS
# termination and to serve as a safety net in front of WhiteNoise (WhiteNoise
# already serves static files efficiently on its own, so Nginx doing it too
# is optional, not required).
#
# Run under systemd (see deploy/onma-chatbot.service) rather than directly,
# so it restarts automatically on crash or server reboot.

set -e
cd "$(dirname "$0")/.."

venv/bin/python manage.py collectstatic --noinput
exec venv/bin/gunicorn onma_bot.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
