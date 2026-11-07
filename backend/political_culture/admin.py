from django.contrib import admin

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
