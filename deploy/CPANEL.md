# Deploying to cPanel (Passenger "Setup Python App")

For a cPanel host with **Setup Python App** (Software section) and **PostgreSQL
Databases** (Databases section) — confirmed available on the target host. If either
is missing, see the notes at the bottom.

This path uses cPanel's own Passenger integration as the WSGI server — `deploy/
run_waitress.bat` and `run_gunicorn.sh` don't apply here, Passenger replaces them.

## 1. Create the PostgreSQL database

cPanel → **Databases → PostgreSQL Databases**.

- Create a database (e.g. `chatbot`) — cPanel will prefix it with your cPanel
  username, giving something like `cpaneluser_chatbot`. That full prefixed name is
  what goes in `.env` as `DB_NAME`.
- Create a database user + password the same way (also gets prefixed, e.g.
  `cpaneluser_chatbot`), then **add that user to the database** with **ALL
  PRIVILEGES** (a separate step on the same page — easy to miss).
- Note the actual Postgres port cPanel uses — often **not** 5432 on shared hosting
  (many hosts run it on a non-default port for isolation). It's usually shown on
  this same page, or check with your host if unclear.

## 2. Create the Python App

cPanel → **Software → Setup Python App** → **Create Application**.

- **Python version**: 3.12 if offered (matches what this project was built/tested
  against) — otherwise the newest 3.x available.
- **Application root**: a folder for the code, e.g. `chatbot_django` (cPanel creates
  it under your home directory).
- **Application URL**: the domain/subdomain/path this should answer on, e.g.
  `chatbot.onmascout.de` or `onmascout.de/chatbot`.
- **Application startup file**: `passenger_wsgi.py` (already in this project's root —
  cPanel scaffolds a generic stub here too; the one in this repo replaces it).
- **Application Entry point**: `application` (matches the variable name in
  `passenger_wsgi.py`).

Creating the app gives you a **virtualenv path** and an **activation command**
(something like `source /home/cpaneluser/virtualenv/chatbot_django/3.12/bin/activate
&& cd /home/cpaneluser/chatbot_django`) — copy that, you'll need it below.

## 3. Upload the code

Any of: Git (cPanel → **Git Version Control**, if this project is in a repo), the
File Manager's upload+extract (zip the project, exclude `venv/`, `db.sqlite3`,
`__pycache__/`, `staticfiles/` — all already in `.gitignore` for this reason), or
SFTP. Upload into the **Application root** folder from step 2.

## 4. Install dependencies

Use cPanel's **Terminal** (Advanced section — usually available even without a
separately-enabled SSH account) or actual SSH if you have it:

```
source /home/cpaneluser/virtualenv/chatbot_django/3.12/bin/activate
cd ~/chatbot_django
pip install -r requirements.txt
```

No Terminal/SSH access at all? The Setup Python App page also has a "Run Pip
Install" box that takes a requirements file path — slower to iterate with, but works.

## 5. Configure `.env`

Copy `.env.example` to `.env` in the application root and fill in real values —
same file this project already uses locally, `python-dotenv` loads it the same way
under Passenger. At minimum:

```
DJANGO_SECRET_KEY=<generate a new one — see below>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=chatbot.onmascout.de

CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://onmascout.de

DATABASE_ENGINE=postgresql
DB_NAME=cpaneluser_chatbot
DB_USER=cpaneluser_chatbot
DB_PASSWORD=<the password you set in step 1>
DB_HOST=localhost
DB_PORT=<the port your host's PostgreSQL actually uses>

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_ENDPOINT=https://api.openai.com/v1/chat/completions
LLM_API_KEY=<a real OpenAI key with billing>
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_ENDPOINT=https://api.openai.com/v1/embeddings

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<your host's SMTP, e.g. mail.onmascout.de>
EMAIL_PORT=587
EMAIL_HOST_USER=<a real mailbox>
EMAIL_HOST_PASSWORD=<its password>
EMAIL_USE_TLS=True
SALES_NOTIFICATION_EMAIL=sales@onmascout.de
```

Generate a fresh secret key rather than reusing the dev one:
```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Once HTTPS is confirmed working on the domain (cPanel → **SSL/TLS Status**, or
AutoSSL), also set `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`,
`CSRF_COOKIE_SECURE=True`, `SECURE_HSTS_SECONDS=31536000`,
`SECURE_HSTS_INCLUDE_SUBDOMAINS=True` — same settings documented in the main
README's "Production deployment" section, same reasoning.

## 6. Migrate, seed, and collect static files

Still in the activated virtualenv from step 4:

```
python manage.py migrate
python manage.py seed_knowledge
python manage.py crawl_site --reindex
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

If any step errors on non-ASCII characters (German umlauts in crawled content) with
a `charmap`/`UnicodeEncodeError`, prefix the command with `PYTHONUTF8=1` — hit and
documented during this project's own Windows-side Postgres migration, may or may not
recur depending on the host's locale configuration.

Static files are served by **WhiteNoise** (already wired into `MIDDLEWARE`), not a
separate cPanel static file mapping — nothing extra to configure there.

## 7. Restart the app

Setup Python App page → **Restart**. (Passenger convention: touching
`tmp/restart.txt` in the app root also triggers a restart, if you'd rather do it
from Terminal without the UI.)

Visit the Application URL from step 2 — `/demo/` and `/admin/` should both respond.

## 8. Schedule the GDPR retention purge

cPanel → **Advanced → Cron Jobs** — much simpler here than the Windows Task
Scheduler / systemd routes in the main README, since cPanel has this built in
natively:

```
0 3 * * *  /home/cpaneluser/virtualenv/chatbot_django/3.12/bin/python /home/cpaneluser/chatbot_django/manage.py purge_old_data
```

(Daily at 3am — adjust the schedule as you like. Use the full venv python path,
not a bare `python`, since cron doesn't activate the virtualenv for you.)

## Known things to test after deploying (host-specific, can't be verified in advance)

- **Streaming timeouts**: shared hosts often put Apache/LiteSpeed proxy timeouts in
  front of Passenger apps that can cut off a long-running `/api/chat/stream/`
  response before it finishes. Test a real chat message after deploying; if it cuts
  off mid-reply, ask your host about increasing the proxy read timeout for this app,
  or reduce `max_tokens` in `bot/llm.py` as a workaround.
- **Outbound HTTPS**: calls to OpenAI/Cloudflare need outbound internet access from
  the app — essentially always allowed on cPanel hosts, but worth confirming if
  anything times out unexpectedly.

## If "Setup Python App" or PostgreSQL Databases isn't actually there

- **No Python App support**: this specific hosting plan cannot run Django at all —
  it's PHP-only shared hosting (same category V1 already sits on). Ask the host if
  it can be enabled, or use a VPS/PaaS instead (see the main README's "Production
  deployment" section for the Gunicorn+Nginx path).
- **No PostgreSQL, only MySQL/MariaDB**: the app currently only supports SQLite or
  PostgreSQL (`DATABASE_ENGINE` in `settings.py`) — MySQL support would need to be
  added first (Django supports it natively, it just isn't wired up in this project
  yet). Ask before proceeding down that path rather than assuming.
