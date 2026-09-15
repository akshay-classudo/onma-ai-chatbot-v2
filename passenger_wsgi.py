"""
Entry point cPanel's "Setup Python App" (Phusion Passenger) looks for at the
application root. Not used by deploy/run_waitress.bat or run_gunicorn.sh —
those are for a self-managed VPS where you run the WSGI server yourself;
here, Passenger *is* the WSGI server and just needs to find `application`.

cPanel auto-generates a stub file with this exact name when you create the
Python App — overwrite it with this content (it's usually scaffolded for a
generic WSGI app, not specifically Django, and needs this import instead).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onma_bot.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
