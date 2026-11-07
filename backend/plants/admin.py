from django.contrib import admin

from plants.models import ChatHistory, Esp32Data, UserMemory, Users


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ["id", "auth_user_id", "latitude", "longitude"]
    search_fields = ["auth_user_id"]


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


@admin.register(Esp32Data)
class Esp32DataAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "analog_value",
        "digital_value",
        "temperature",
        "humidity",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__auth_user_id"]
    raw_id_fields = ["user"]
    date_hierarchy = "created_at"
