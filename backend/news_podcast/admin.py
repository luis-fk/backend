from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import AdminTextareaWidget
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.html import format_html_join
from django.utils.safestring import SafeString
from django.utils.text import Truncator

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.messages import brl
from news_podcast.models import (
    Area,
    Episode,
    Feed,
    PodcastSettings,
    SettingsMissing,
    Topic,
)

LONG_PROMPTS = ["selection_prompt", "script_prompt"]
NUMBERS = [
    "speech_speed",
    "text_input_price",
    "text_output_price",
    "fallback_input_price",
    "fallback_output_price",
    "voice_input_price",
    "voice_output_price",
]


class PodcastSettingsForm(forms.ModelForm):
    class Meta:
        model = PodcastSettings
        fields = "__all__"
        widgets = {
            **{name: AdminTextareaWidget(attrs={"rows": 30}) for name in LONG_PROMPTS},
            # As narrow as the minutes.
            **{
                name: forms.NumberInput(attrs={"class": "vIntegerField"})
                for name in NUMBERS
            },
        }


@admin.register(PodcastSettings)
class PodcastSettingsAdmin(admin.ModelAdmin):
    form = PodcastSettingsForm
    fieldsets = [
        (None, {"fields": ["paused"]}),
        ("Episode", {"fields": [("min_minutes", "max_minutes", "speech_speed")]}),
        (
            "Models",
            {
                "description": "Text models are provider:model, with google_genai "
                "or openai (a bare gemini-* name means google_genai); the voice "
                "model too, with google_genai, the only voice provider. Prices in "
                "US$ per million tokens, from each provider's price list; the "
                "history computes each run's cost with them.",
                # Each model, then its prices in the row below.
                "fields": [
                    "text_model",
                    ("text_input_price", "text_output_price"),
                    "fallback_model",
                    ("fallback_input_price", "fallback_output_price"),
                    "voice_model",
                    ("voice_input_price", "voice_output_price"),
                ],
            },
        ),
        (
            "Prompts",
            {
                "fields": [
                    "selection_prompt",
                    "script_prompt",
                    "expand_prompt",
                    "voice_style",
                    "headline_voice_style",
                ]
            },
        ),
    ]

    # A single row, which only seed_news_podcast creates. These permissions must not
    # query the database: the admin checks them on every page, for its menu.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: PodcastSettings | None = None
    ) -> bool:
        return False

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        # Django checks the permission only in the list it renders, after the row
        # would have been read and its link or the seed message shown.
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        # The list goes straight to the form of the single row.
        try:
            podcast_settings = PodcastSettings.load()
        except SettingsMissing as error:
            self.message_user(request, str(error), messages.ERROR)
            return super().changelist_view(request, extra_context)
        return redirect(
            "admin:news_podcast_podcastsettings_change", podcast_settings.pk
        )


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ["outlet", "section", "url", "active"]
    list_editable = ["active"]
    list_filter = ["section", "active"]
    search_fields = ["outlet", "url"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "position"]
    list_editable = ["position"]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["title", "area", "position", "active", "taught"]
    list_editable = ["position", "active"]
    list_filter = ["area", "active"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Topic]:
        return super().get_queryset(request).with_taught_at().select_related("area")

    # A topic is taught when a sent lesson row points to it.
    @admin.display(description="taught on (Brasília)", ordering="taught_at")
    def taught(self, topic: Topic) -> str:
        # The annotation from with_taught_at(), which the stubs can't see.
        taught_at = getattr(topic, "taught_at")
        if taught_at is None:
            return "-"
        return f"{taught_at.astimezone(LOCAL_TZ):%d/%m/%Y}"


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = [
        "started",
        "kind",
        "status",
        "length",
        "pace",
        "cost",
        "short_error",
    ]
    list_filter = ["kind", "status"]
    date_hierarchy = "started_at"
    fields = [
        "started",
        "kind",
        "status",
        "topic",
        "story_title",
        "page_list",
        "length",
        "script_words",
        "pace",
        "cost",
        "cost_usd",
        "usage",
        "error",
    ]
    readonly_fields = ["started", "page_list", "length", "pace", "cost"]

    # The history is written by the runs only.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Episode | None = None
    ) -> bool:
        return False

    @admin.display(description="started (Brasília)", ordering="started_at")
    def started(self, episode: Episode) -> str:
        return f"{episode.started_at.astimezone(LOCAL_TZ):%d/%m/%Y %H:%M}"

    @admin.display(description="length")
    def length(self, episode: Episode) -> str:
        if episode.duration_seconds is None:
            return "-"
        minutes, seconds = divmod(round(episode.duration_seconds), 60)
        return f"{minutes}:{seconds:02d}"

    # At speed 1.0, the voice's own pace, the one NATURAL_WORDS_PER_MINUTE stands for.
    @admin.display(description="words/min")
    def pace(self, episode: Episode) -> str:
        if not episode.script_words or not episode.duration_seconds:
            return "-"
        return f"{episode.script_words / (episode.duration_seconds / 60):.0f}"

    @admin.display(description="cost", ordering="cost_usd")
    def cost(self, episode: Episode) -> str:
        # A non-breaking space keeps "R$" with the number in the narrow column.
        return brl(episode.cost_usd).replace(" ", "\N{NO-BREAK SPACE}")

    @admin.display(description="error")
    def short_error(self, episode: Episode) -> str:
        return Truncator(episode.error).chars(80)

    @admin.display(description="pages")
    def page_list(self, episode: Episode) -> SafeString | str:
        if not episode.pages:
            return "-"
        # Text, not links: the URLs come from a web search.
        return format_html_join(
            "\n",
            "{}: {}<br>",
            ((page.get("title", ""), page.get("url", "")) for page in episode.pages),
        )

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        response = super().changelist_view(request, extra_context)
        # A redirect or an error page has no list to add up.
        if isinstance(response, TemplateResponse) and "cl" in response.context_data:
            listed = response.context_data["cl"].queryset
            total = listed.aggregate(total=Sum("cost_usd"))["total"] or 0
            response.context_data["total_cost"] = brl(total)
        return response
