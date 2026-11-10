from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.http import HttpRequest

from plants.models import ChatHistory, Esp32Data, UserMemory, Users


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "auth_user_id", "active", "latitude", "longitude"]
    list_filter = ["active"]
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
