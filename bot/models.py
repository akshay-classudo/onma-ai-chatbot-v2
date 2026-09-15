from django.db import models

LANGUAGE_CHOICES = [
    ("de", "German"),
    ("en", "English"),
]


class ChatSession(models.Model):
    session_token = models.CharField(max_length=64, unique=True)
    ip_partial = models.CharField(max_length=45, blank=True, null=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="de")
    lead_prompted = models.BooleanField(
        default=False,
        help_text="Whether the lead-capture form has already been offered in this session (shown at most once).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.session_token[:12] + "…"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    detected_language = models.CharField(
        max_length=5, blank=True,
        help_text="Auto-detected from this message's text (user messages only). Blank for assistant replies.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class KnowledgeEntry(models.Model):
    """
    Knowledge snippet for one language, editable from the admin instead of
    hardcoded in a config file. Active + retrievable entries are chunked and
    embedded into KnowledgeChunk rows (via the "Reindex" admin action or
    `manage.py reindex_knowledge`); chat requests then do a real similarity
    search over those chunks instead of concatenating everything.

    Either hand-typed (source_url blank) or crawled from the real site
    (source_url set — see `manage.py crawl_site`, which also fills
    `checksum` and `last_crawled_at` and only touches its own rows on
    re-crawl, never hand-typed ones).
    """

    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    retrievable = models.BooleanField(
        default=True,
        help_text=(
            "Include this entry's content in vector-search retrieval. Turn "
            "off for meta/behavior-rule entries that should not compete for "
            "relevance against a visitor's question — those belong in code "
            "as always-on instructions instead."
        ),
    )
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(
        max_length=100, blank=True,
        help_text="Optional grouping (e.g. SEO/SEA/Webdesign). Set automatically by the crawler when detectable.",
    )
    source_url = models.URLField(
        max_length=500, blank=True, null=True, unique=True,
        help_text="Set automatically by manage.py crawl_site. Blank for hand-typed entries.",
    )
    checksum = models.CharField(
        max_length=64, blank=True,
        help_text="SHA-256 of the crawled content, used to detect real changes on re-crawl.",
    )
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["language", "order", "id"]
        verbose_name_plural = "Knowledge entries"

    def __str__(self):
        return f"[{self.language}] {self.title}"


class KnowledgeChunk(models.Model):
    """
    One embeddable slice of a KnowledgeEntry's content. Rebuilt from scratch
    each time the entry is reindexed (old chunks for that entry are deleted
    and replaced) — this table is derived data, never edited directly.
    """

    entry = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE, related_name="chunks")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    content = models.TextField()
    embedding = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entry__order", "id"]

    def __str__(self):
        return f"{self.entry.title} chunk #{self.pk}"


class Lead(models.Model):
    """
    A lead captured via the widget's in-chat form (triggered by keyword-based
    sales-intent detection in views.chat, see lead_detection.py) or logged
    manually by an admin.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("closed", "Closed"),
    ]

    session = models.ForeignKey(
        ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    service_interest = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    consent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the visitor ticked the lead form's own consent checkbox (separate from cookie consent).",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or self.email or f"Lead #{self.pk}"


class AnswerCache(models.Model):
    """
    Shared across ALL sessions — keyed on (language, normalized question
    text) only, not on session or conversation history. A cache hit skips
    both the embedding call and the LLM call entirely. See
    bot/answer_cache.py for the normalization + hashing logic.
    """

    question_hash = models.CharField(max_length=64, unique=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    question_text = models.TextField(blank=True, help_text="Normalized question, kept for admin visibility.")
    answer = models.TextField()
    sources_json = models.JSONField(blank=True, null=True)
    hit_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-hit_count", "-created_at"]

    def __str__(self):
        return f"[{self.language}] {self.question_text[:50]}"


class BotSettings(models.Model):
    """
    Singleton (always pk=1) — admin-editable overrides for things that would
    otherwise need a .env edit + server restart. Every field here is
    optional: blank means "fall through to the .env/settings.py value" (see
    bot/settings_store.py's resolve() and get_bot_settings()), so this table
    can start empty without breaking anything, and an admin only needs to
    fill in the fields they actually want to override.

    Secrets stored here (llm_api_key, smtp_password) are plain-text columns,
    same trust boundary as .env — anyone with admin access already has full
    control of the site, so this isn't a new exposure, just a different
    place credentials live.
    """

    # Branding — read by the public /api/config/ endpoint, applied by the
    # widget on load (bot/static/bot/widget.js).
    bot_name = models.CharField(
        max_length=100, blank=True,
        help_text="Overrides the widget header title (e.g. \"ONMA scout Assistant\"). Blank = widget's own per-language default.",
    )
    bot_icon = models.ImageField(
        upload_to="bot_settings/", blank=True, null=True,
        help_text="Overrides the default ONMA logo avatar shown for bot messages. Blank = the bundled onma.png.",
    )

    # LLM provider — read by bot/llm.py on every call, so a change here
    # takes effect on the very next chat message, no restart needed.
    llm_api_key = models.CharField(max_length=255, blank=True, help_text="Overrides LLM_API_KEY from .env.")
    llm_model = models.CharField(max_length=100, blank=True, help_text="e.g. gpt-4o-mini, or openai/gpt-4o-mini for OpenRouter. Overrides LLM_MODEL.")
    llm_endpoint = models.URLField(max_length=300, blank=True, help_text="Overrides LLM_ENDPOINT.")
    embedding_model = models.CharField(max_length=100, blank=True, help_text="Overrides EMBEDDING_MODEL.")
    embedding_endpoint = models.URLField(max_length=300, blank=True, help_text="Overrides EMBEDDING_ENDPOINT.")

    # Email / SMTP — read when sending a lead notification (views.lead_create).
    sales_notification_email = models.EmailField(blank=True, help_text="Where lead notifications are sent. Overrides SALES_NOTIFICATION_EMAIL.")
    smtp_host = models.CharField(max_length=255, blank=True, help_text="Overrides EMAIL_HOST.")
    smtp_port = models.PositiveIntegerField(blank=True, null=True, help_text="Overrides EMAIL_PORT.")
    smtp_user = models.CharField(max_length=255, blank=True, help_text="Overrides EMAIL_HOST_USER.")
    smtp_password = models.CharField(max_length=255, blank=True, help_text="Overrides EMAIL_HOST_PASSWORD.")
    smtp_use_tls = models.BooleanField(default=True, help_text="Overrides EMAIL_USE_TLS — only applies if an SMTP host is set above.")
    default_from_email = models.EmailField(blank=True, help_text="Overrides DEFAULT_FROM_EMAIL.")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot settings"
        verbose_name_plural = "Bot settings"

    def __str__(self):
        return "Bot settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
