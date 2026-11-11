from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Max, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from plants.models import ChatHistory, Esp32Data, Esp32Device, UserMemory, Users

NO_LOCATION = "No location: readings come without the weather"


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
        "device",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__auth_user_id"]
    raw_id_fields = ["user"]
    date_hierarchy = "created_at"


def usernames(auth_user_ids: list[int]) -> dict[int, str]:
    """The auth usernames of these ids, read in one query on the auth database."""
    return dict(
        get_user_model()
        ._default_manager.filter(pk__in=auth_user_ids)
        .values_list("pk", "username")
    )


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Esp32Device
        fields = ["nickname", "user", "dry_value", "wet_value", "active"]
        labels = {"user": "Person"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # The people who can use plants, by name; a device's current owner stays
        # listed, so a blocked owner's device can still be edited.
        people = Users.objects.filter(Q(active=True) | Q(pk=self.instance.user_id))
        names = usernames(list(people.values_list("auth_user_id", flat=True)))
        person = self.fields["user"]
        person.queryset = people
        person.choices = [
            ("", "---------"),
            *sorted(
                ((user.pk, names.get(user.auth_user_id, "-")) for user in people),
                key=lambda choice: choice[1],
            ),
        ]
        person.help_text = "Among the people who can use plants."


@admin.register(Esp32Device)
class Esp32DeviceAdmin(admin.ModelAdmin):
    form = DeviceForm
    list_display = ["nickname", "person", "active", "last_reading", "location"]
    list_filter = ["active"]
    actions = ["new_key"]
    empty_value_display = "-"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Esp32Device]:
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .annotate(last_reading_at=Max("readings__created_at"))
        )

    def get_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        fields = ["nickname", "user", "dry_value", "wet_value", "active"]
        return fields if obj is None else [*fields, "prefix", "location"]

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        return [] if obj is None else ["prefix", "location"]

    @admin.display(description="person")
    def person(self, obj: Esp32Device) -> str:
        return usernames([obj.user.auth_user_id]).get(obj.user.auth_user_id, "-")

    @admin.display(description="last reading")
    def last_reading(self, obj: Any) -> Any:
        return getattr(obj, "last_reading_at", None)

    @admin.display(description="location")
    def location(self, obj: Esp32Device) -> str:
        return "-" if obj.user.latitude and obj.user.longitude else NO_LOCATION

    def save_model(
        self, request: HttpRequest, obj: Any, form: forms.ModelForm, change: bool
    ) -> None:
        if not change:
            obj.new_key = obj.generate_key()
        super().save_model(request, obj, form, change)

    def response_add(
        self, request: HttpRequest, obj: Any, post_url_continue: str | None = None
    ) -> HttpResponse:
        # The key goes in this response, not in a message: Django keeps messages
        # in a cookie that is signed but readable.
        return self.key_page(request, obj, obj.new_key)

    # Only someone who may change devices can take a device's key.
    @admin.action(description="Generate a new key", permissions=["change"])
    def new_key(
        self, request: HttpRequest, queryset: QuerySet[Esp32Device]
    ) -> HttpResponse | None:
        # A new key keeps the device, and with it the plant's history.
        if queryset.count() != 1:
            self.message_user(
                request, "Pick one device to give a new key.", messages.ERROR
            )
            return None
        device = queryset.get()
        key = device.generate_key()
        device.save(update_fields=["prefix", "key_hash"])
        return self.key_page(request, device, key)

    def key_page(
        self, request: HttpRequest, device: Esp32Device, key: str
    ) -> HttpResponse:
        context = {
            **self.admin_site.each_context(request),
            "title": f"Key of {device.nickname}",
            "key": key,
        }
        return TemplateResponse(
            request, "admin/plants/esp32device/key_created.html", context
        )
