# ONMA scout Chatbot — V2 (Django)

Same chat widget as V1, rebuilt on Django to get an admin panel for free.
This is the **foundation-first** slice of the V2 build guide — it covers the
admin panel and a cleaner data model, not the full V2 checklist. See
"What's still deferred" below.

## What this is (and isn't)

**Included:**

- Django admin at `/admin/` to manage:
  - **Knowledge entries** — the source content per language (DE/EN), editable
    without touching code (replaces V1's hardcoded `system_prompts.php`)
  - **Knowledge chunks** — read-only, shows how each entry was split and
    whether it has an embedding yet (derived data, rebuilt by reindexing)
  - **Chat sessions** and a flat **chat message** log (read-only, for support/QA)
  - **Leads** — captured automatically by the widget (see below) or logged manually
- The exact same widget UI as V1 (`bot/static/bot/widget.js` + `.css`), bilingual DE/EN toggle included
- **Real RAG**: knowledge entries are chunked, embedded (OpenAI `text-embedding-3-small`
  by default), and stored as vectors; each chat message is embedded and matched against
  those chunks by cosine similarity (see "How the RAG works" below) — not pgvector
  (see why below), but real retrieval, not a static concatenated blob
- Source citations: the chat API returns a `sources` array (chunk titles + similarity
  score) alongside the reply, and the widget shows them under the answer
- **Automatic lead capture**: keyword-based sales-intent detection on each user message
  (see "How lead capture works" below) triggers an in-widget name/email/phone form at
  most once per session, saved to the `Lead` model with its own consent timestamp, plus
  an email notification to the sales inbox
- **Security + GDPR hardening** (see below for full detail): prompt-injection-resistant
  context framing, a GDPR retention purge command, a right-to-erasure endpoint + admin
  action, env-driven production security settings, and a custom check against
  accidentally deploying with CORS wide open
- **Real content ingestion**: `manage.py crawl_site` pulls actual page content from
  onmascout.de into Knowledge entries — real phone/email/address/hours, real service
  copy — replacing the hand-typed placeholders (see "How content ingestion works" below)
- **ONMA scout–branded admin**: custom header/title/index title and the ONMA logo in the
  admin's own color (see "Admin branding" below)
- **Automatic language detection**: each message's language is detected from its own text
  (not the DE/EN toggle) and drives the reply, retrieval, and lead-keyword language for
  that turn — see "How language detection works" below for why a general-purpose
  detector was tried and rejected in favor of a targeted DE/EN approach
- **Answer caching**: repeated questions (normalized, shared across all sessions) skip
  both the embedding and LLM calls entirely — see "How answer caching works"
- **Streamed responses**: `/api/chat/stream/` (Server-Sent Events) — the widget now
  renders the reply as it arrives instead of waiting for the full answer; `/api/chat/`
  still exists for non-streaming clients — see "How streaming works"
- **Cloudflare Turnstile**: optional bot protection on both chat endpoints, off by
  default (needs real keys) — see "How Turnstile works"
- **Admin-editable settings**: LLM API key/model/endpoint, bot name/icon, and
  email/SMTP — all overridable from Admin → Bot → Bot settings, no `.env` edit or
  restart needed — see "Admin-editable settings (BotSettings)"

**Explicitly deferred** (still on the V2 build guide, not built here):

- A full sitemap crawl (the real sitemap is dominated by thousands of programmatically
  generated city/service landing pages — see below for why the default crawl is a
  curated page list instead, and how to opt into more)
- pgvector (see below for why brute-force search is used instead, and when to revisit)
- An OS-level scheduled task actually running the retention purge cron (the command
  exists — see below — wiring it to Windows Task Scheduler/cron is an infra step, not code)
- Choosing/contracting an EU-hosted LLM+embedding provider, and adding the chatbot to
  the company's Verzeichnis von Verarbeitungstätigkeiten — legal/business decisions,
  not something to build
- Full production QA pass (load testing, cross-browser, etc.)

## How the RAG works

1. **Admin edits a Knowledge entry** (Admin → Bot → Knowledge entries) — plain text content per language.
2. **Reindexing** splits that entry's content into paragraph-sized chunks (`bot/chunker.py`)
   and calls the OpenAI embeddings API for each chunk, storing the resulting vector on a
   `KnowledgeChunk` row (`bot/indexing.py`). Trigger this either via the admin action
   ("Reindex embeddings for selected entries" on the Knowledge entries list) or
   `python manage.py reindex_knowledge` (add `--language de` to limit to one language).
   This is a deliberate, explicit step — not automatic on save — so an admin edit
   doesn't silently trigger a network call and doesn't break if the API is briefly down.
3. **On each chat message**, the message itself is embedded and compared (cosine
   similarity, `bot/retrieval.py`) against every chunk for that language; the top
   `RAG_TOP_K` chunks scoring at or above `RAG_SIMILARITY_THRESHOLD` (both configurable
   in `.env`) are inserted into the system prompt as "Context", alongside the always-on
   persona/grounding rules (`BASE_INSTRUCTIONS` in `views.py` — these apply regardless of
   what's retrieved, so the "don't invent facts" rule can't be crowded out by a
   low-relevance match).
4. If nothing clears the threshold, the model is told no matching content was found —
   it still answers, but per its instructions must admit it doesn't know rather than guess.

**Why brute-force cosine similarity instead of pgvector:** the guide's V2 spec targets a
whole crawled site (hundreds+ of chunks), which needs a real vector index. This
foundation's knowledge base is a handful of hand-typed entries — a full Python scan over
all embeddings on every request is fast enough at that scale and avoids requiring a
PostgreSQL install. Swap `bot/retrieval.py`'s `retrieve()` for a pgvector query later if
the corpus grows enough (real site crawl, many pages) that a full scan stops being fast.

## How content ingestion works

`manage.py crawl_site` fetches real pages from onmascout.de and turns them into
`KnowledgeEntry` rows, so the bot answers from the site's actual text instead of
hand-typed placeholders.

**Why it doesn't crawl the whole sitemap by default:** onmascout.de's sitemap
(`sitemap.xml` → 12+ sub-sitemaps) is dominated by thousands of programmatically
generated city × service landing pages (`ads-agentur-berlin`, `ads-agentur-zuerich`,
`keyword-berlin`, ...) — near-duplicate SEO pages, not distinct knowledge. Ingesting all
of them would balloon embedding cost and fill retrieval with redundant, competing
chunks. So by default the crawler fetches a curated list of the real informational pages
instead — `DEFAULT_PATHS` in `bot/management/commands/crawl_site.py`: homepage, about,
services overview, the four service pages (SEO/SEA/Webdesign/App), online marketing,
contact, hours, and the four biggest city pages (Berlin/Hamburg/Köln/Frankfurt).

**`/blogs/` and `/lexikon/` were evaluated and deliberately excluded**: `/blogs/` is a
thin index — real content lives across 78 individual articles of uneven quality, not the
index page itself, so crawling just the index would add near-zero value (same failure
mode as the below-threshold `/ueber-uns/` page). `/lexikon/` turned out to be a genuine
surprise: a **~14MB, 8.3-million-character** generic online-marketing glossary — real
content, but far too large and too generic (definitions of general marketing terms, not
facts about ONMA scout specifically) to be worth the embedding cost of thousands of
chunks. The city pages, by contrast, checked out as genuinely substantive (~5.6KB each,
city-specific service copy) and are now included.

**Usage:**

```
python manage.py crawl_site                    # curated pages, DE, no reindex
python manage.py crawl_site --reindex           # also chunk+embed what changed
python manage.py crawl_site --full-sitemap --limit 50   # opt into the real sitemap, capped
```

**How it works:**

1. `bot/sitemap_crawler.py` can fetch and flatten a sitemap index (only used with `--full-sitemap`).
2. `bot/html_extractor.py` fetches each page and extracts real content with BeautifulSoup:
   strips `<script>/<style>/<nav>/<header>/<footer>/<form>` entirely, drops anything whose
   class/id looks like a cookie banner or menu, then pulls heading/paragraph/list text from
   what's left — headings become `## Heading` lines so crawled content reads like the
   hand-typed entries. It also line-filters a few cookie-notice phrasings that survive
   class-based stripping (custom banners without a recognizable class name).
3. Each page becomes (or updates) one `KnowledgeEntry`, matched by `source_url`. A
   SHA-256 `checksum` of the extracted text means **re-running the crawl only touches
   entries whose real content changed** — unchanged pages are left alone (`updated_at`
   doesn't even bump), and hand-typed entries (no `source_url`) are never touched at all.
4. Pages yielding under 150 characters of real content are skipped, not saved — this
   crawler only fetches static HTML (no JS execution), so a page whose real content is
   client-side-rendered comes back nearly empty and gets reported as a failure with that
   explanation, rather than silently saving a near-blank entry. (`/ueber-uns/` hits this on
   the real site.)
5. **Not automatic**: nothing re-crawls on a schedule yet — run it by hand, or add it to
   the same Task Scheduler setup as `purge_cron.bat` (see Security + GDPR hardening) if
   you want it recurring.

**Already run once in this environment:** the 10 curated pages plus the 4 city pages were
crawled and successfully reindexed (150 real embedded chunks total, verified against
OpenRouter — see Setup). Two things needed a manual follow-up after the first crawl run,
both already done:

- `/ueber-uns/` came back below the 150-char threshold (its real content is JS-rendered)
  — its earlier, pre-threshold near-empty entry was deactivated by hand.
- The hand-typed **Unternehmensinformationen** and **Leistungsübersicht** placeholder
  entries (`[Telefonnummer einsetzen]` and friends) are now superseded by real crawled
  content (`/kontakt/` has the actual phone/email/address, `/offnungszeiten/` the actual
  hours) — deactivated so the bot can never surface a placeholder to a real visitor. They're
  still visible in the admin (just `is_active=False`) if you want to restore or edit them.

**Known limitation:** extraction is generic (not onmascout.de-specific), so some crawled
entries carry a little residual noise — a two-line "Home / Page Name" breadcrumb at the
top of most pages, since this theme doesn't mark its breadcrumb with a recognizable class
name. Cosmetic, not incorrect; left as-is rather than chasing every site-specific quirk.

### Adding one URL from the admin (no terminal needed)

Admin → Bot → Knowledge entries has an **"Add from URL"** button next to "Add knowledge
entry" (top right of the list). It opens a small form — paste a page URL, pick a language,
optionally set a category, and (checked by default) it chunks + embeds the page
immediately after saving, so it's answerable right away with no separate reindex step.

This uses the exact same extraction as `crawl_site` — `bot/ingest_url.py` holds the shared
"fetch → extract → save-or-update-by-checksum" logic, and both the management command and
this admin view call it, so behavior never drifts between the two (same 150-character
minimum-content rejection, same checksum-based re-fetch-is-a-no-op-if-unchanged behavior).
Verified end-to-end: added `/leistungen/google-ads-adwords/` this way — a real onmascout.de
page not in the curated `DEFAULT_PATHS` list — and it came in at 57KB of real content,
correctly chunked into 84 pieces, embedded immediately, and is retrievable exactly the same
way `crawl_site`-ingested pages are.

Use this for one-off pages worth including that aren't part of the curated crawl list
(guide's own spec: "Add/import a URL manually, supplement to the crawler") — for adding
many pages at once, `crawl_site` (or extending `DEFAULT_PATHS`) is still the right tool.

## How lead capture works

1. Every user chat message is checked against a small keyword list per language
   (`bot/lead_detection.py`) — pricing/consultation-shaped phrases like "kosten",
   "Angebot", "Beratung" (DE) or "price", "quote", "consultation" (EN). It also guesses
   a `service_interest` (SEO/SEA/Webdesign/App) from a second keyword pass.
2. The keyword list checked is chosen by the `language` the client sent with the
   message (the DE/EN toggle) — **not** detected from the message text itself. Typing
   German words while the toggle is set to English won't trigger it; this matches the
   rest of the app's "no content-based language detection yet" approach.
3. On the first match in a session, the chat response includes `lead_prompt` and the
   session is flagged `lead_prompted` so it never asks again — even across page
   reloads (the flag lives server-side on the session, not in the browser).
4. The widget renders a small form (name, email, phone, its own consent checkbox —
   separate from cookie consent) under the bot's reply. Submitting posts to
   `POST /api/lead/`, which requires `consent: true` and at least an email or phone,
   saves a `Lead` row with `consent_at`, and emails `SALES_NOTIFICATION_EMAIL` (prints
   to the console by default — set real `EMAIL_*` / `EMAIL_BACKEND` env vars for
   actual delivery).
5. Visitors can dismiss the form ("No, thanks") without submitting; nothing is saved,
   and (per point 3) they won't be asked again this session either.

## Security + GDPR hardening

**Already true without any new code** (verified, not just assumed):

- No API key or secret anywhere in `bot/static/` (client-side code) — confirmed by grep.
- No raw SQL anywhere in the app — every query goes through the Django ORM, which
  parameterizes automatically.
- The widget renders every piece of dynamic content (LLM replies, source titles, lead
  form text) via `.textContent`, never string-concatenated into `innerHTML` — an LLM
  reply or a knowledge-entry title can't inject markup into the page.
- Django admin has CSRF protection on by default (`CsrfViewMiddleware` + `{% csrf_token %}`
  in every admin form) — nothing extra was needed for that checklist item.
- Nothing logs the API key or request headers — `bot/llm.py`'s error messages only
  include the provider's own HTTP status/response body, never what we sent.

**Built this pass:**

- **Prompt-injection framing**: retrieved context is now wrapped in explicit
  `<<<CONTEXT_START>>>`/`<<<CONTEXT_END>>>` markers with a rule (`BASE_INSTRUCTIONS`,
  point 5) telling the model to treat everything between them as reference data, never
  as instructions — even if it's phrased as one. Matters because knowledge entries could
  in principle contain adversarial text (e.g. if someone with limited admin access, or a
  future crawler, ever introduces attacker-controlled content).
- **`RETENTION_DAYS` + `manage.py purge_old_data`**: deletes `ChatSession` rows (cascades
  their `ChatMessage`s) older than `RETENTION_DAYS` (default 90). `--dry-run` reports
  without deleting; `--days N` overrides the setting for one run. **Leads are untouched**
  — a lead has its own consent/retention basis, separate from chat-log retention.
  This is the command; actually running it on a schedule needs an OS-level cron/Task
  Scheduler entry (infra, not code) — see below for how.
- **`DELETE /api/session/<token>/`** (right-to-erasure): deletes a session, its messages,
  and any `Lead` tied to it. The session token is the same unguessable 32-byte secret
  used everywhere else in this API — knowing it is already treated as sufficient
  authorization for that session, so this doesn't need separate auth. Same action is also
  available as an admin bulk action ("Erase selected sessions") on the Chat sessions list,
  for support staff handling a request without touching the API directly.
- **Env-driven production security settings**: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`/`SECURE_HSTS_INCLUDE_SUBDOMAINS` all default
  to off (so local HTTP dev keeps working) but are wired to env vars — flipping them for
  a real TLS deployment is a config change, not a code change. Run
  `python manage.py check --deploy` before going live; it flags exactly these until
  they're set, plus the rest of Django's own deployment checklist (verified: currently
  reports all 5 as expected in this dev setup).
- **`bot/checks.py`**: a custom check (`bot.W001`) that fires on any `manage.py` command
  if `CORS_ALLOW_ALL_ORIGINS=True` while `DEBUG=False` — catches the specific "wide-open
  CORS shipped to production" mistake that Django's own `--deploy` checklist can't, since
  it doesn't know about django-cors-headers.

**Scheduling the purge command (Windows Task Scheduler, since this runs on XAMPP/Windows):**
`schtasks /tr` runs a single command line and has no separate "working directory" flag, so
`purge_cron.bat` (already in this folder) `cd`s to its own location (`%~dp0`) before
running — no hardcoded path to update if the project moves:

```
schtasks /create /tn "ONMA chatbot GDPR purge" /sc daily /st 03:00 ^
  /tr "C:\xampp\htdocs\german ai chatbot\chatbot_django\purge_cron.bat"
```

(Run from an elevated prompt.)

## Admin branding

`bot/admin.py` sets `admin.site.site_header/site_title/index_title` to ONMA scout
branding, and `bot/templates/admin/base_site.html` overrides the header to add the
ONMA logo and a favicon, plus `bot/static/admin/onma_admin.css` recolors Django admin's
CSS custom properties (`--primary`, `--header-bg`, `--link-fg`, etc.) to the widget's
blue in both light and dark admin themes.

**Why `bot` is listed before `django.contrib.admin` in `INSTALLED_APPS`**: Django's
app-directories template loader returns the _first_ matching template it finds across
`INSTALLED_APPS`, in order. With `django.contrib.admin` first, its own
`admin/base_site.html` shadowed ours completely — the override was invisible until the
order was flipped. If you ever add another app that also ships an `admin/` template
override, the same rule applies: put it before `django.contrib.admin`.

## Admin-editable settings (BotSettings)

Admin → Bot → Bot settings — a single-row settings screen (a real Django singleton
model, not the generic key-value `bot_settings` table from the original build guide's
V2 schema; a typed model gives proper widgets — password-masked API key/SMTP fields,
an image upload for the icon — that a generic key-value table can't) for things that
would otherwise need a `.env` edit and a server restart:

- **Branding**: `bot_name` (overrides the widget's header title) and `bot_icon` (an
  uploaded image overriding the default ONMA logo avatar)
- **LLM provider**: `llm_api_key`, `llm_model`, `llm_endpoint`, `embedding_model`,
  `embedding_endpoint` — lets an admin switch providers or rotate a key without
  touching `.env`
- **Email/SMTP**: `sales_notification_email`, `smtp_host`/`port`/`user`/`password`/
  `use_tls`, `default_from_email` — for the lead-notification email specifically

**Every field is optional and blank by default** — `bot/settings_store.py`'s
`resolve(db_value, env_value)` returns the DB value only if it's non-blank, otherwise
falls through to the existing `.env`-backed `django.conf.settings` value. This means
the table can start (and stay) empty without changing any existing behavior; an admin
only fills in the fields they actually want to override. `bot/llm.py` calls this on
every request (no caching — a single indexed-PK lookup is cheap enough to just do
fresh each time, which sidesteps the classic multi-worker cache-staleness problem
entirely rather than needing Redis/Memcached as new infrastructure just for this).

**Public branding endpoint**: `GET /api/config/` returns only `bot_name` and
`bot_icon_url` — never the API key or SMTP credentials, even though they live on the
same row. `widget.js` fetches this once on load and re-applies the header title and
any already-rendered bot avatars if a custom name/icon is set; a brief moment showing
the built-in defaults before this resolves is expected and harmless.

**Verified end-to-end**, including a real mistake along the way worth keeping as a
cautionary note: a real admin API key override was tested by setting `llm_api_key` to
an obviously-fake value and confirming the app actually used it (a real 401 came back
from the provider, proving the DB value — not `.env` — was sent). Separately, while
exploring the new admin page for the first time, the `bot_name` field was set to a
real custom value ("onma scout") but `llm_api_key` ended up containing what looks like
the admin's own auto-generated superuser password rather than a real API key — almost
certainly a mistaken paste — which **broke live chat** until spotted and cleared (the
`bot_name` change was kept; only the API key field was reset to blank, falling back to
the working `.env` key). Worth remembering: this table overriding `.env` means a wrong
value here fails the same way a wrong `.env` value would, just without needing a
restart to take effect *or* to undo.

**Known limitation**: `bot_icon` uploads are served by a plain Django view
(`onma_bot/urls.py`, see `settings.py`'s `MEDIA_ROOT` comment) rather than WhiteNoise —
adequate for a handful of small icon files, not meant to scale to heavy media use.

## How language detection works

Each chat message's language is auto-detected from its own text (`bot/language_detection.py`)
and used for that turn's reply, retrieval, fallback message, and lead-intent keywords —
**not** simply taken from the client's DE/EN toggle. The toggle is still sent and used as
the fallback when detection can't tell (an empty result, a one-word or emoji-only
message), and it still controls the widget's own UI chrome (buttons, placeholders).

**Why a general-purpose detector was tried and rejected**: `langdetect` (55 languages)
was evaluated first and repeatedly misclassified clearly-German business-chat sentences
as Afrikaans, Latvian, or Lithuanian — closely-related-language confusion that got worse,
not better, with realistic short chat text ("Wie viel kostet SEO?" → Afrikaans at 99.9%
confidence). Since only DE/EN are ever actually in play here, `language_detection.py`
instead runs a targeted marker-word vote between exactly those two languages: 12/12
correct on a hand-built test set of realistic short messages, versus langdetect's
repeated misfires on the same set. `ChatMessage.detected_language` records what was
detected per message (visible/filterable in the admin's Chat messages log) so detection
quality is easy to audit over time; `/api/chat/` and `/api/chat/stream/` both also
return `detected_language` in their response for the same reason.

## How answer caching works

`bot/answer_cache.py` hashes `(language, normalized question)` — lowercased, trailing
punctuation stripped, whitespace collapsed — and checks `AnswerCache` before doing any
embedding or LLM call. A hit skips both entirely and returns the stored answer/sources
immediately (`"cached": true` in the API response); a miss proceeds normally and, on a
real LLM success, stores the result for `ANSWER_CACHE_TTL_SECONDS` (default 24h).

**Scope, deliberately**: the cache is shared across every session — many different
visitors asking "what does SEO cost?" all hit the same cached answer — and keyed only on
the message text, ignoring conversation history. A question that only makes sense given
prior turns won't normalize to a key anyone else would produce, so it naturally falls
through to a real LLM call; this cache is for FAQ-style repeats, not full conversations.
Lead-intent detection still runs on a cache hit (it only looks at the incoming message,
same as any other turn). Set `ANSWER_CACHE_ENABLED=False` to disable outright; expired
rows are swept by `manage.py purge_old_data` (disk hygiene — the cache holds no personal
data, so this isn't a privacy requirement the way session retention is). Admin →
Bot → Answer cache is read-only; delete a row there to force-bust that one question.

## How streaming works

`POST /api/chat/stream/` returns `Content-Type: text/event-stream` and streams the reply
as it's generated, instead of `/api/chat/`'s one blocking JSON response (which still
exists, for any non-browser client that just wants a single response). Frame shapes:

```
data: {"delta": "..."}                                                    — zero or more, in order
data: {"done": true, "sources": [...]|null, "lead_prompt": {...}|null, "cached": bool, "detected_language": "de"|"en"}
```

A cache hit or an LLM failure still fits this same shape — one `delta` frame carrying the
whole text, then `done` — rather than a separate protocol, so `widget.js` only needs one
parsing path regardless of how the reply was actually produced. `bot/llm.py`'s
`stream_chat_completion()` parses the provider's own SSE format (`data: {...}`, terminated
by `data: [DONE]`) and yields text deltas as they arrive.

**Widget side**: `_streamReply()` reads the response body via `fetch` + `ReadableStream` +
`TextDecoder`, splitting on blank lines to find complete frames and appending each delta
to a growing bubble. Browsers without `ReadableStream`/`TextDecoder` (feature-detected up
front) transparently fall back to `_fetchReplyClassic()` against the plain `/api/chat/`
endpoint — same UX, just not incremental.

**Testing note**: the cache-hit and LLM-failure paths were verified first (before a
working LLM key existed), as a proxy — same frame-parsing logic, just one delta instead
of many. Once real credits became available (via OpenRouter — see Setup), genuine
multi-chunk token-by-token streaming was verified for real too, and that real test
**did catch a bug the proxy testing couldn't**: `requests` defaults to Latin-1 for
`text/event-stream` responses that don't specify a charset, silently mangling every
non-ASCII character (a German reply's umlauts came through as e.g. `fÃ¼r`
instead of `für` — double-encoded mojibake). Fixed in `stream_chat_completion()` by
explicitly setting `response.encoding = "utf-8"` before iterating — every OpenAI-compatible
provider actually sends UTF-8 regardless of what the header omits. `chat_completion()` and
`embed_texts()` were never affected (they use `response.json()`, which decodes bytes
independently of `.encoding`) — this was specific to `iter_lines(decode_unicode=True)`.
Worth remembering: a passing proxy test only proves what it actually exercises: this one
never sent real non-ASCII content through the decode path, so it couldn't have caught this.

## How Turnstile works

`bot/turnstile.py`'s `verify_turnstile_token()` is a no-op (always returns true) unless
**both** `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are set — same env-gated,
off-by-default pattern as this project's other production-only hardening. When enabled,
both chat endpoints reject with `403 {"error": "turnstile_failed"}` if the client's
`turnstile_token` doesn't verify against Cloudflare's `siteverify` API.

**Widget side**: if `ONMAChat.init({ turnstileSiteKey: '...' })` is set, the widget lazily
loads Cloudflare's real script and renders one **invisible** Turnstile widget (no visible
checkbox in normal cases — Cloudflare's own risk engine decides if an interactive
challenge is ever needed). Before every send, `_getTurnstileToken()` re-executes it to get
a fresh, single-use token and attaches it to the request. If `turnstileSiteKey` isn't
configured, none of this runs — zero cost, zero external script load, matching the
server's own default-disabled behavior.

**On network/service failure** (Cloudflare's verify endpoint itself is unreachable, not
"token rejected"): controlled by `TURNSTILE_FAIL_OPEN` (default `True`) — fails open
(allows the message through) so a Cloudflare outage doesn't take the whole chat down.
Set `TURNSTILE_FAIL_OPEN=False` to fail closed instead, if availability matters less than
guaranteed bot-blocking for your case.

**Getting real keys**: sign up at
[the Cloudflare dashboard's Turnstile section](https://dash.cloudflare.com/?to=/:account/turnstile),
create a site, and set `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` in `.env` to the
values it gives you — no code changes needed.

**Testing note**: unlike Turnstile itself, this integration _was_ fully verified
end-to-end — Cloudflare publishes official test key pairs that work without any account,
and both were exercised for real in a browser against Cloudflare's live verification API:

- `1x00000000000000000000BB` / `1x0000000000000000000000000000000AA` (always passes) —
  confirmed the full pipeline (real script load → real invisible challenge → real token →
  real server-side verification → request proceeds normally)
- `2x00000000000000000000BB` / `2x0000000000000000000000000000000AA` (always blocks) —
  confirmed the same pipeline correctly ends in `403` and the widget shows its normal
  error/retry state
  These test keys are also listed in `.env.example` for whenever you want to re-verify the
  integration locally without touching a real Cloudflare account.

## Production deployment

Everything below was actually set up and tested on this machine — not just written as
theoretical instructions.

### Database: PostgreSQL

SQLite (the dev default) doesn't handle concurrent writes well under a real multi-worker
WSGI server and has no replication story, so production uses PostgreSQL. Switching is one
settings block (`onma_bot/settings.py`) gated by `DATABASE_ENGINE=postgresql` in `.env`:

```
DATABASE_ENGINE=postgresql
DB_NAME=onma_chatbot
DB_USER=onma_chatbot
DB_PASSWORD=<real password>
DB_HOST=localhost
DB_PORT=5432
```

**Already done in this environment**: PostgreSQL 17 was installed (`winget install
PostgreSQL.PostgreSQL.17`), a dedicated `onma_chatbot` database and role created (not
using the `postgres` superuser directly), and all existing data — 22 knowledge entries,
312 embedded chunks, cached answers, the admin account — migrated over from SQLite via
`dumpdata`/`loaddata` rather than starting fresh (avoids re-spending embedding API calls).
Verified end-to-end afterward: real RAG chat request against Postgres returned a correct,
grounded, source-cited answer.

**Windows-specific gotcha hit during this**: `manage.py dumpdata` failed with a
`'charmap' codec can't encode` error — Windows defaults Python's file I/O to cp1252,
which can't represent the German umlauts in the crawled content, even with
`PYTHONIOENCODING=utf-8` set (that only affects stdout/stdin/stderr, not arbitrary file
opens). Fixed with `PYTHONUTF8=1` instead (Python's UTF-8 mode, forces UTF-8 for all
file I/O, not just the standard streams) — needed for `dumpdata`/`loaddata`/
`collectstatic` on Windows whenever non-ASCII content is involved.

If migrating your own data later: `python manage.py dumpdata --natural-foreign
--natural-primary -e contenttypes -e auth.permission -e sessions --output=dump.json`
(add `PYTHONUTF8=1` in front on Windows) while still pointed at the old database, switch
`.env`, `migrate` the new one, then `loaddata dump.json`.

### Static files: WhiteNoise

`manage.py runserver` serves static files itself in dev and ignores `STATIC_ROOT`
entirely — that stops working the moment a real WSGI server is in front (neither
Waitress nor Gunicorn serve static files on their own). Added WhiteNoise
(`whitenoise.middleware.WhiteNoiseMiddleware`, right after `SecurityMiddleware`) with
`CompressedManifestStaticFilesStorage`, so `manage.py collectstatic` produces
content-hashed, pre-compressed files that get served with a one-year immutable
`Cache-Control` — no separate Nginx/IIS static config, S3 bucket, or CDN needed for a
project this size.

**Verified**: ran the app under real Waitress (not `runserver`) with `DJANGO_DEBUG=False`
— `collectstatic` produced hashed filenames (e.g. `widget.8fa6ff3e3dcc.css`), WhiteNoise
served them with `Cache-Control: max-age=315360000, public, immutable`, and the full chat
flow (session, chat, streaming) still worked correctly end-to-end against Postgres.

### WSGI server + reverse proxy

`manage.py runserver` refuses to be a production server (Django's own docs are explicit
about this). `deploy/` has both paths — pick based on where this actually ends up hosted:

- **Linux** (most VPS/PaaS options): `deploy/run_gunicorn.sh` (Gunicorn) +
  `deploy/onma-chatbot.service` (systemd, auto-restart on crash/reboot) +
  `deploy/nginx.conf.example` (TLS termination + reverse proxy). The Nginx example
  specifically disables proxy buffering on `/api/chat/stream/` — without that, Nginx
  buffers the entire SSE response before forwarding it, silently defeating streaming.
- **Windows** (staying on the current setup's OS): `deploy/run_waitress.bat` (Waitress —
  Gunicorn doesn't run on Windows at all, it needs `fcntl`/`fork`). Wrap it with
  [NSSM](https://nssm.cc/) to run as a proper Windows Service instead of a console window
  that dies on logout; put IIS or Apache in front for TLS.

Both scripts run `collectstatic` before starting, and both bind to `127.0.0.1` only —
the reverse proxy is what's actually internet-facing, never the Django app directly. That
assumption is also why `SECURE_PROXY_SSL_HEADER` is safe to set unconditionally in
`settings.py` (trusts `X-Forwarded-Proto` from the proxy to know a request was really
HTTPS) — it would be a spoofing risk if the app were reachable bypassing the proxy, but
it isn't.

**Gunicorn note**: `--timeout 60` in `run_gunicorn.sh` matters — the default 30s would
kill a slow LLM streaming response mid-flight. Default sync workers also hold one
connection per streaming request for its full duration; fine at this project's expected
traffic, worth revisiting (async workers, e.g. `gunicorn -k uvicorn.workers.UvicornWorker`
with an ASGI setup) only if concurrent chat volume grows substantially.

### Flipping the remaining security settings

These stay off by default so plain HTTP local dev keeps working — flip them once a real
TLS domain exists (verify with `python manage.py check --deploy`, confirmed to correctly
flag all of these plus `bot.W001` for CORS when unset):

```
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-real-domain.com
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://onmascout.de
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
```

Plus: a real OpenAI key with billing (swap back from OpenRouter — see Setup), real SMTP
credentials (swap from the console `EMAIL_BACKEND`), and real Cloudflare Turnstile keys
if bot protection is wanted publicly.

### Deploying to cPanel

If the target host is cPanel with **Setup Python App** (Passenger) and **PostgreSQL
Databases** available, `deploy/CPANEL.md` has the complete step-by-step for that
specific path — creating the database, wiring up `passenger_wsgi.py` (already in this
project's root), `.env` values, migrating, and scheduling the GDPR purge via cPanel's
native Cron Jobs UI instead of Task Scheduler/systemd. It also covers what to check
first if Python App support or PostgreSQL isn't actually on the plan (common on
cheaper shared hosting — Django can't run there at all if Python App support is
missing, regardless of wanting cPanel specifically).

### Not done here (needs real infrastructure this machine doesn't have)

- An actual domain + DNS + TLS certificate (Let's Encrypt is free and standard on Linux;
  the Nginx example assumes one already exists)
- Actual hosting to run any of this on — a VPS (Hetzner/DigitalOcean/Linode) or a
  Django-friendly PaaS (Render/Railway/Fly.io); shared PHP hosting like V1's typically
  can't run a Django/WSGI app at all
- Automated Postgres backups (`pg_dump` on a schedule, or the host's built-in backup
  feature) — the local Postgres install here has none configured, it's a dev/staging copy
- Error monitoring (e.g. Sentry) — errors currently only reach `storage`-less local logs
- Actually scheduling `purge_cron.bat`'s Linux equivalent (a cron entry, same idea) on
  whatever server this ends up on

## Setup

```
cd chatbot_django
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # then fill in LLM_API_KEY
python manage.py migrate
python manage.py seed_knowledge   # loads starter DE/EN knowledge entries
python manage.py reindex_knowledge  # chunks + embeds them (needs LLM_API_KEY with credits)
python manage.py createsuperuser  # your own admin login
python manage.py runserver 127.0.0.1:8000
```

This project was already set up once in this environment:

- Dependencies installed in `venv/`
- Database migrated (SQLite, `db.sqlite3`), seeded with starter knowledge entries, then
  10 real pages crawled from onmascout.de on top (see "How content ingestion works")
- **Currently configured for OpenRouter, for testing** (the original OpenAI account had
  no credits — every call failed with 429 `insufficient_quota`). `.env` is set to
  `LLM_ENDPOINT=https://openrouter.ai/api/v1/chat/completions`,
  `EMBEDDING_ENDPOINT=https://openrouter.ai/api/v1/embeddings`,
  `LLM_MODEL=openai/gpt-4o-mini`, `EMBEDDING_MODEL=openai/text-embedding-3-small` — all
  four confirmed working directly against OpenRouter's live API (chat, streaming, _and_
  embeddings all verified for real, not just assumed). **Switch to OpenAI for
  production** by changing just those four values back to `LLM_ENDPOINT` =
  `https://api.openai.com/v1/chat/completions`, `EMBEDDING_ENDPOINT` =
  `https://api.openai.com/v1/embeddings`, and dropping the `openai/` prefix from both
  model names — plus a real OpenAI key with credits. No code changes either way:
  `bot/llm.py` only ever reads these settings, it has no OpenRouter- or OpenAI-specific
  code path.
- `python manage.py reindex_knowledge` has been run against OpenRouter successfully —
  150 real embedded chunks now exist across 14 active, retrievable German knowledge
  entries (10 core pages + 4 city pages — see "How content ingestion works"), and RAG
  answers are genuinely grounded (verified: asking for contact details returns the real
  crawled phone/email/address with correct source citations; asking whether a specific
  city is served returns a real, city-specific answer citing that city's own page).
  Re-run this any time knowledge entries change, or after switching providers (embeddings
  from different providers/models aren't comparable — a provider switch invalidates
  existing chunks' vectors for meaningful similarity search, though nothing enforces that
  automatically here; reindex fully after switching rather than assuming old chunks are
  still valid).
- **English knowledge is still thin** (2 hand-typed entries, ~800 characters total) — the
  real site has no English pages to crawl, so this wasn't addressed by ingestion. Worth a
  dedicated pass (hand-authoring richer English entries covering the same ground as the
  German crawled content) if English-speaking visitors are expected to ask anything
  beyond the most generic questions.
- A superuser was created: **username `admin`**, password shown once in the terminal when it was created — log in at `/admin/` and change it immediately (`/admin/password_change/`) since it was auto-generated.
- Fixed a pre-existing bug in the scaffolded `settings.py`: `startproject` had generated a
  `MAILERS` dict, which isn't a real Django setting (the actual one is `EMAIL_BACKEND` —
  Django silently ignored `MAILERS` entirely, so email would have defaulted to SMTP
  against `localhost:25` and failed). Now uses real `EMAIL_BACKEND`/`EMAIL_HOST`/etc.
  settings, console backend by default.
- The dev server is running at **http://127.0.0.1:8000/** (`python manage.py runserver`, from `venv`) — stop it with Ctrl+C in its terminal, or find and kill the `python.exe manage.py runserver` process if it's running in the background.

## Try it

- Demo widget: http://127.0.0.1:8000/demo/
- Admin panel: http://127.0.0.1:8000/admin/

## Editing the bot's knowledge

Go to **Admin → Bot → Knowledge entries**. Each row is one piece of source
content for one language. After adding or editing content:

1. Tick the row(s) and run the **"Reindex embeddings for selected entries"**
   action (or `python manage.py reindex_knowledge`) — this is what actually
   makes the new content answerable; editing alone doesn't re-embed it.
2. Check **Admin → Bot → Knowledge chunks** to confirm the entry now has
   chunks with "Embedded" = yes.

Turn `retrievable` off for an entry to exclude it from vector search (its
content still shows in the admin, just never competes for relevance against
a visitor's question) — useful for meta/reference notes that aren't meant
to be quoted back.

The **Source** column shows "Hand-typed" or "Crawled" — the latter means
`source_url`/`checksum`/`last_crawled_at` are set (see "How content ingestion
works" above). A hand-edit to a crawled entry's content is safe from being
silently discarded by routine re-crawls (the crawler only overwrites when the
_live page's own text_ changes, since the comparison is against the stored
checksum from the last crawl, not against your edit) — but it will get
overwritten the next time the real page's content actually changes and
someone runs `crawl_site` again. For an edit that should never be touched by
the crawler, clear its `source_url` (making it a plain hand-typed entry) or
add a separate hand-typed entry instead.

**Embeddings need the same OpenAI credits as chat completions** — if the
account has no credits, reindexing will report a per-entry error (visible in
the admin action's message and in `reindex_knowledge`'s output) but won't
crash; chunks just won't get embeddings until credits are available, and
until then the bot answers with no retrieved context (still honest about not
knowing, per its instructions — just not grounded in anything).

## Embedding the widget elsewhere (e.g. on onmascout.de)

```html
<link rel="stylesheet" href="http://127.0.0.1:8000/static/bot/widget.css" />
<script src="http://127.0.0.1:8000/static/bot/widget.js"></script>
<script>
  ONMAChat.init({
    apiBase: "http://127.0.0.1:8000", // swap for the real Django host
    hasConsent: function () {
      return document.cookie.includes("cookie_consent=accepted");
    },
  });
</script>
```

Cross-origin embedding requires the Django host in `CORS_ALLOWED_ORIGINS`
(or `CORS_ALLOW_ALL_ORIGINS=True`, the dev default — **lock this down**
before production, per the build guide's security checklist).

## Folder structure

```
chatbot_django/
  manage.py
  requirements.txt
  .env / .env.example
  purge_cron.bat       # Task Scheduler wrapper for purge_old_data
  passenger_wsgi.py     # entrypoint for cPanel's Setup Python App (Passenger)
  deploy/
    run_waitress.bat    # Windows production entrypoint (self-managed VPS)
    run_gunicorn.sh      # Linux production entrypoint (self-managed VPS)
    onma-chatbot.service # systemd unit (Linux)
    nginx.conf.example   # reverse proxy + TLS termination example (Linux)
    CPANEL.md            # step-by-step for cPanel + Passenger + PostgreSQL hosting
  onma_bot/            # Django project (settings, urls, wsgi)
  bot/                 # the app
    models.py          # ChatSession, ChatMessage, KnowledgeEntry, KnowledgeChunk, Lead, AnswerCache, BotSettings
    admin.py            # admin panel registration + branding + reindex/erase actions + BotSettings singleton
    views.py            # /api/session/, /api/chat/[/stream/], /api/lead/, /api/config/, /demo/, BASE_INSTRUCTIONS
    llm.py              # provider-specific LLM + embedding + streaming calls, isolated for swapping
    settings_store.py    # get_bot_settings() / resolve() — DB-over-.env config overrides
    chunker.py          # paragraph-packing text chunker
    retrieval.py        # cosine-similarity search over KnowledgeChunk
    indexing.py          # shared chunk+embed logic (admin action & mgmt command)
    lead_detection.py    # keyword-based sales-intent detection
    language_detection.py  # DE/EN marker-word detection (see "How language detection works")
    answer_cache.py      # question normalization + hashing + cache read/write
    turnstile.py         # Cloudflare Turnstile server-side verification
    sitemap_crawler.py   # fetch + flatten a sitemap.xml (index or urlset)
    html_extractor.py    # generic boilerplate-stripping HTML -> knowledge text
    ingest_url.py         # shared "fetch+extract+save one URL" logic (crawl_site + admin's Add from URL)
    forms.py             # AddFromUrlForm
    checks.py           # custom manage.py check: CORS wide-open outside DEBUG
    utils.py            # IP anonymization
    management/commands/seed_knowledge.py
    management/commands/reindex_knowledge.py
    management/commands/crawl_site.py
    management/commands/purge_old_data.py
    static/bot/         # widget.js, widget.css, onma.png (same as V1, + citations/lead form/streaming/Turnstile)
    static/admin/onma_admin.css   # admin color theme
    templates/bot/demo.html
    templates/admin/base_site.html   # admin branding override (logo, favicon)
    templates/admin/bot/knowledgeentry/change_list.html   # "Add from URL" button
    templates/admin/bot/knowledgeentry/add_from_url.html  # the form itself
```

## Relationship to the PHP V1 app

The `chatbot/` (PHP) app is untouched and still works standalone on XAMPP.
This Django app is a separate, independently-runnable project — nothing here
depends on PHP/MySQL/XAMPP. Run either one, or both side by side (V1 on
Apache :8080, V2 on Django :8000) while you decide which one to keep.

Database: PostgreSQL
Switch off SQLite. SQLite is fine for this foundation/dev phase, but it doesn't handle concurrent writes well under a real multi-worker WSGI server, has no replication/multi-server story, and file-based backups are fragile at scale. PostgreSQL is the standard choice for Django in production, and it's also the natural path if you ever outgrow the current brute-force similarity search and want real pgvector (already noted as the upgrade path in bot/retrieval.py's docstring). Switching is just a DATABASES setting change + pip install psycopg[binary] + migrate — the data itself (16 knowledge entries, leads, etc.) is small enough to just re-seed/re-crawl rather than migrate row-by-row.

Already built, just needs real values flipped in .env
Setting Dev value Production value
LLM_ENDPOINT/EMBEDDING_ENDPOINT/LLM_MODEL/EMBEDDING_MODEL OpenRouter (testing) Back to OpenAI's endpoints, drop the openai/ prefix from model names, real OpenAI key with billing — then run reindex_knowledge once
DJANGO_DEBUG True False
DJANGO_ALLOWED_HOSTS localhost,127.0.0.1 your real domain
DJANGO_SECRET_KEY dev key generate a fresh one — never reuse the dev value
CORS_ALLOW_ALL_ORIGINS/CORS_ALLOWED_ORIGINS allow-all False + your site's real origin only
SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE False True (once HTTPS is confirmed working)
SECURE_HSTS_SECONDS 0 e.g. 31536000 (1 year), plus SECURE_HSTS_INCLUDE_SUBDOMAINS=True
TURNSTILE_SITE_KEY/TURNSTILE_SECRET_KEY blank (disabled) real keys from your Cloudflare dashboard
EMAIL_BACKEND + EMAIL_HOST/etc. console (prints, doesn't send) real SMTP — a transactional service (SendGrid, Mailgun, Amazon SES) so lead emails actually arrive
Run python manage.py check --deploy after — it's Django's own checklist and will flag anything still unset.

Genuinely new infrastructure (not just config)
WSGI server: manage.py runserver explicitly refuses to be a production server. You need Gunicorn (Linux) or Waitress (if staying on Windows — Gunicorn doesn't run there) behind a reverse proxy.
Reverse proxy + TLS: Nginx (Linux) or IIS (Windows) terminating HTTPS — a real cert (Let's Encrypt is free and standard).
Hosting: shared PHP hosting (like whatever V1 sits on) typically can't run Django. You'd need a VPS (DigitalOcean/Hetzner/Linode) or a PaaS with good Django support (Render, Railway, Fly.io).
Process manager: something to keep the app running and auto-restart on crash — systemd (Linux) or NSSM (Windows service wrapper).
collectstatic: runserver serves static files itself in dev; production needs manage.py collectstatic + the reverse proxy (or WhiteNoise) serving them.
Real cron/Task Scheduler entry for purge_cron.bat (or its Linux equivalent) — the script exists and is tested, it just isn't actually scheduled yet.
Backups: automated Postgres backups (pg_dump on a schedule, or your host's built-in backup feature).
Error monitoring (optional but recommended): something like Sentry, since right now errors only go to a local log file.
Business/legal, not infrastructure
If full GDPR compliance matters, the original build guide flags: an EU-hosted LLM+embedding provider (Azure OpenAI EU region, Mistral EU) or a signed DPA with OpenAI, and adding this chatbot to the company's Verzeichnis von Verarbeitungstätigkeiten. Not something I can do — worth flagging to whoever owns compliance.
Want me to start on any of these — e.g., wiring up Postgres support (DATABASES config + psycopg + a .env var to pick SQLite vs Postgres), or setting up collectstatic/WhiteNoise for static files?
