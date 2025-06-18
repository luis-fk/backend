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

admin.site.register(Texts)
admin.site.register(TextWordCount)
admin.site.register(UserMemory)
admin.site.register(Users)
admin.site.register(IdeologiesDefinition)
admin.site.register(TextChunks)
admin.site.register(ChatHistory)
