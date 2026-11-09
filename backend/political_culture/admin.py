from django.contrib import admin
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
    list_display = ["id", "auth_user_id"]
    search_fields = ["auth_user_id"]


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
