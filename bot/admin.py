from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse

from .forms import AddFromUrlForm
from .indexing import reindex_entries, reindex_entry
from .ingest_url import IngestError, ingest_url
from .llm import LlmError
from .models import AnswerCache, BotSettings, ChatMessage, ChatSession, KnowledgeChunk, KnowledgeEntry, Lead

admin.site.site_header = "ONMA scout Admin"
admin.site.site_title = "ONMA scout Admin"
admin.site.index_title = "Chatbot-Verwaltung"


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("role", "content", "created_at")
    readonly_fields = ("role", "content", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_token", "language", "ip_partial", "message_count", "lead_prompted", "created_at",
    )
    list_filter = ("language", "lead_prompted", "created_at")
    search_fields = ("session_token",)
    readonly_fields = ("session_token", "ip_partial", "created_at")
    inlines = [ChatMessageInline]
    actions = ["erase_selected"]

    @admin.display(description="Messages")
    def message_count(self, obj):
        return obj.messages.count()

    @admin.action(description="Erase selected sessions (GDPR right-to-erasure)")
    def erase_selected(self, request, queryset):
        """Same semantics as DELETE /api/session/<token>/ — deletes the
        session (cascades its messages) and any Lead tied to it."""
        session_count = queryset.count()
        Lead.objects.filter(session__in=queryset).delete()
        queryset.delete()
        self.message_user(
            request, f"Erased {session_count} session(s), their messages, and any linked leads.",
            level=messages.SUCCESS,
        )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Flat chat log viewer across all sessions."""

    list_display = ("session", "role", "short_content", "detected_language", "created_at")
    list_filter = ("role", "detected_language", "created_at")
    search_fields = ("content", "session__session_token")
    readonly_fields = ("session", "role", "content", "detected_language", "created_at")

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80] + ("…" if len(obj.content) > 80 else "")

    def has_add_permission(self, request):
        return False


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "title", "language", "category", "source", "is_active", "retrievable",
        "order", "chunk_count", "last_crawled_at", "updated_at",
    )
    list_filter = ("language", "is_active", "retrievable", "category")
    search_fields = ("title", "content", "source_url")
    list_editable = ("is_active", "retrievable", "order")
    readonly_fields = ("source_url", "checksum", "last_crawled_at")
    actions = ["reindex_selected"]
    change_list_template = "admin/bot/knowledgeentry/change_list.html"

    @admin.display(description="Source")
    def source(self, obj):
        return "Crawled" if obj.source_url else "Hand-typed"

    @admin.display(description="Chunks")
    def chunk_count(self, obj):
        return obj.chunks.count()

    @admin.action(description="Reindex embeddings for selected entries")
    def reindex_selected(self, request, queryset):
        total_chunks, errors = reindex_entries(queryset)

        if total_chunks:
            self.message_user(
                request, f"Reindexed {queryset.count()} entries into {total_chunks} chunks.",
                level=messages.SUCCESS,
            )
        for entry, exc in errors:
            self.message_user(
                request, f"Failed to reindex [{entry.language}] {entry.title}: {exc}",
                level=messages.ERROR,
            )

    def get_urls(self):
        custom_urls = [
            path(
                "add-from-url/",
                self.admin_site.admin_view(self.add_from_url_view),
                name="bot_knowledgeentry_add_from_url",
            ),
        ]
        return custom_urls + super().get_urls()

    def add_from_url_view(self, request):
        """Admin-only: fetch one arbitrary URL, extract its content
        (bot/html_extractor.py, same as manage.py crawl_site), save it as a
        KnowledgeEntry, and optionally chunk+embed it immediately — the V2
        guide's "Add/import a URL manually (supplement to the crawler)"."""
        if request.method == "POST":
            form = AddFromUrlForm(request.POST)
            if form.is_valid():
                url = form.cleaned_data["url"]
                language = form.cleaned_data["language"]
                category = form.cleaned_data["category"]

                try:
                    entry, status = ingest_url(url, language, category)
                except IngestError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                    return redirect("admin:bot_knowledgeentry_add_from_url")

                verb = {"created": "Added", "updated": "Updated", "unchanged": "No change to"}[status]
                self.message_user(
                    request, f'{verb} knowledge entry from {url}: "{entry.title}".',
                    level=messages.SUCCESS,
                )

                if form.cleaned_data["reindex_now"]:
                    try:
                        chunk_count = reindex_entry(entry)
                        self.message_user(
                            request, f"Reindexed into {chunk_count} chunk(s).",
                            level=messages.SUCCESS,
                        )
                    except LlmError as exc:
                        self.message_user(
                            request, f"Saved, but reindexing failed: {exc}",
                            level=messages.WARNING,
                        )

                return redirect("admin:bot_knowledgeentry_change", entry.pk)
        else:
            form = AddFromUrlForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Add knowledge entry from URL",
            "form": form,
            "opts": self.model._meta,
        }
        return render(request, "admin/bot/knowledgeentry/add_from_url.html", context)


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    """Read-only — chunks are derived data, rebuilt by reindexing the entry."""

    list_display = ("entry", "language", "short_content", "has_embedding", "updated_at")
    list_filter = ("language",)
    search_fields = ("content", "entry__title")
    readonly_fields = ("entry", "language", "content", "embedding", "updated_at")

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80] + ("…" if len(obj.content) > 80 else "")

    @admin.display(description="Embedded", boolean=True)
    def has_embedding(self, obj):
        return obj.embedding is not None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "name", "email", "phone", "service_interest", "status", "consent_at", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "phone")
    readonly_fields = ("session", "consent_at", "created_at")
    list_editable = ("status",)


@admin.register(AnswerCache)
class AnswerCacheAdmin(admin.ModelAdmin):
    """Delete a row to force-bust the cache for that question; content is
    derived (produced by a real LLM call), not meant to be hand-edited."""

    list_display = ("question_text", "language", "hit_count", "created_at", "expires_at")
    list_filter = ("language",)
    search_fields = ("question_text", "answer")
    readonly_fields = ("question_hash", "language", "question_text", "answer", "sources_json", "hit_count", "created_at", "expires_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    """Singleton — always exactly one row (enforced by the model's save()
    pinning pk=1). The changelist redirects straight to that row's change
    form (or the add form, the very first time) instead of showing a list
    of one, since there's never anything to select between."""

    fieldsets = (
        ("Branding", {"fields": ("bot_name", "bot_icon")}),
        ("LLM provider (overrides .env when set)", {
            "fields": ("llm_api_key", "llm_model", "llm_endpoint", "embedding_model", "embedding_endpoint"),
        }),
        ("Email / SMTP (overrides .env when set)", {
            "fields": (
                "sales_notification_email", "smtp_host", "smtp_port", "smtp_user",
                "smtp_password", "smtp_use_tls", "default_from_email",
            ),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name in ("llm_api_key", "smtp_password"):
            if field_name in form.base_fields:
                form.base_fields[field_name].widget = forms.PasswordInput(render_value=True)
        return form

    def has_add_permission(self, request):
        return not BotSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        existing = BotSettings.objects.first()
        if existing:
            return redirect(reverse("admin:bot_botsettings_change", args=[existing.pk]))
        return redirect(reverse("admin:bot_botsettings_add"))
