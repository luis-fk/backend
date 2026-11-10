from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.http import HttpRequest

from political_culture.api.word_counter.service import analyse_again
from political_culture.models import (
    ChatHistory,
    IdeologiesDefinition,
    TextChunks,
    Texts,
    TextWordCount,
    UserMemory,
    Users,
)


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "auth_user_id"]
    search_fields = ["auth_user_id"]
    search_help_text = "Search by name or by the auth user id."

    @admin.display(description="name")
    def name(self, obj: Users) -> str:
        name: str | None = (
            get_user_model()
            ._default_manager.filter(pk=obj.auth_user_id)
            .values_list("username", flat=True)
            .first()
        )
        return name or "-"

    def get_search_results(
        self, request: HttpRequest, queryset: QuerySet[Users], search_term: str
    ) -> tuple[QuerySet[Users], bool]:
        found, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        name = search_term.strip()
        if name:
            # The names live in the auth database, so their ids are read there first.
            ids = list(
                get_user_model()
                ._default_manager.filter(username__icontains=name)
                .values_list("pk", flat=True)
            )
            found |= queryset.filter(auth_user_id__in=ids)
        return found, may_have_duplicates


@admin.register(Texts)
class TextsAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "author", "ideology", "user_submitted_text", "user"]
    list_filter = ["ideology", "user_submitted_text"]
    search_fields = ["title", "author", "ideology"]
    raw_id_fields = ["user"]
    actions = ["analyse_selected_again"]

    @admin.action(description="Analyse again (title, author, summary, word count)")
    def analyse_selected_again(
        self, request: HttpRequest, queryset: QuerySet[Texts]
    ) -> None:
        for text in queryset:
            analyse_again(text)
        self.message_user(request, f"{queryset.count()} text(s) analysed again.")


@admin.register(TextWordCount)
class TextWordCountAdmin(admin.ModelAdmin):
    list_display = ["id", "text", "total_word_count"]
    search_fields = ["text__title"]
    raw_id_fields = ["text"]


@admin.register(IdeologiesDefinition)
class IdeologiesDefinitionAdmin(admin.ModelAdmin):
    list_display = ["id", "ideology"]
    search_fields = ["ideology"]


@admin.register(TextChunks)
class TextChunksAdmin(admin.ModelAdmin):
    list_display = ["id", "text"]
    raw_id_fields = ["text"]


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "role", "message"]
    list_filter = ["role"]
    search_fields = ["message"]
    raw_id_fields = ["user"]


@admin.register(UserMemory)
class UserMemoryAdmin(admin.ModelAdmin):
    list_display = ["id", "user"]
    raw_id_fields = ["user"]
