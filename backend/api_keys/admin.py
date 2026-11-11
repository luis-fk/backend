from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from api_keys.app_users import USERS_MODELS, apps_of, ids_in_apps, set_apps
from api_keys.models import ApiKey

User = get_user_model()


def apps_field(help_text: str, required: bool = False) -> forms.MultipleChoiceField:
    return forms.MultipleChoiceField(
        choices=[(app, app) for app in USERS_MODELS],
        widget=forms.CheckboxSelectMultiple,
        required=required,
        help_text=help_text,
    )


def username(auth_user_id: int | None) -> str:
    if auth_user_id is None:
        return "-"
    name: str | None = (
        User._default_manager.filter(pk=auth_user_id)
        .values_list("username", flat=True)
        .first()
    )
    return name or "-"


class ApiKeyAddForm(forms.ModelForm):
    person = forms.ModelChoiceField(
        queryset=User._default_manager.filter(is_active=True).order_by("username"),
        help_text="The person the key acts as, among those whose Active is ticked.",
    )
    apps = apps_field(
        "The apps the key works in; the person must be able to use each.",
        required=True,
    )

    class Meta:
        model = ApiKey
        fields = ["name"]

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        person = cleaned_data.get("person")
        chosen = cleaned_data.get("apps")
        if person and chosen:
            ids = ids_in_apps(person.pk, chosen)
            missing = [app for app in chosen if app not in ids]
            if missing:
                self.add_error(
                    "apps",
                    f"{person} can't use {', '.join(missing)}: their user page gives "
                    "the access.",
                )
            cleaned_data["users"] = ids
        return cleaned_data

    def save(self, commit: bool = True) -> ApiKey:
        self.instance.auth_user_id = self.cleaned_data["person"].pk
        self.instance.users = self.cleaned_data["users"]
        key: ApiKey = super().save(commit)
        return key


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "person",
        "app_list",
        "prefix",
        "active",
        "created_at",
        "last_used_at",
    ]
    list_editable = ["active"]
    list_filter = ["active"]

    @admin.display(description="person")
    def person(self, obj: ApiKey) -> str:
        return username(obj.auth_user_id)

    @admin.display(description="apps")
    def app_list(self, obj: ApiKey) -> str:
        # In the apps' order: PostgreSQL's jsonb doesn't keep the keys' order.
        return ", ".join(app for app in USERS_MODELS if app in obj.users)

    def get_form(
        self,
        request: HttpRequest,
        obj: ApiKey | None = None,
        change: bool = False,
        **kwargs: Any,
    ) -> type[forms.ModelForm]:
        # The person and the apps are chosen once, when the key is created.
        if obj is None:
            kwargs["form"] = ApiKeyAddForm
        return super().get_form(request, obj, change, **kwargs)

    def get_fields(self, request: HttpRequest, obj: ApiKey | None = None) -> list[str]:
        if obj is None:
            return ["name", "person", "apps"]
        return [
            "name",
            "person",
            "app_list",
            "prefix",
            "active",
            "created_at",
            "last_used_at",
        ]

    def get_readonly_fields(
        self, request: HttpRequest, obj: ApiKey | None = None
    ) -> list[str]:
        if obj is None:
            return []
        return ["person", "app_list", "prefix", "created_at", "last_used_at"]

    def save_model(
        self, request: HttpRequest, obj: ApiKey, form: forms.ModelForm, change: bool
    ) -> None:
        if not change:
            obj.new_key = obj.generate_key()
        super().save_model(request, obj, form, change)

    def response_add(
        self, request: HttpRequest, obj: ApiKey, post_url_continue: str | None = None
    ) -> HttpResponse:
        # Shows the key in this response rather than in a message: Django keeps
        # messages in a cookie that is signed but readable, so the key would travel
        # in it.
        context = {
            **self.admin_site.each_context(request),
            "title": f"API key {obj.name}",
            "key": obj.new_key,
        }
        return TemplateResponse(
            request, "admin/api_keys/apikey/key_created.html", context
        )


class UserCreationWithAppsForm(AdminUserCreationForm):
    apps = apps_field("The apps the person can sign in to.")


class UserChangeWithAppsForm(UserChangeForm):
    apps = apps_field(
        "Unticking an app blocks the person in it at once. Their data there stays, "
        "and ticking the app again gives it back."
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["apps"].initial = apps_of(self.instance.pk)
        # The form of an admin who can only view users has no model fields.
        if "is_active" in self.fields:
            self.fields["is_active"].help_text = (
                "Unticked, the person can't use any app or the admin, at once. Their "
                "data stays."
            )


# The admin's user pages, with the apps each person can use: Django's own, which
# the auth app registers first, plus an apps field next to Active, since both
# decide what the person can use.
admin.site.unregister(User)


@admin.register(User)
class UserWithAppsAdmin(UserAdmin):
    add_form = UserCreationWithAppsForm
    form = UserChangeWithAppsForm
    add_fieldsets = (*UserAdmin.add_fieldsets, ("Apps", {"fields": ("apps",)}))
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Access", {"fields": ("is_active", "apps")}),
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    list_display = (*UserAdmin.list_display, "is_active", "app_list")
    list_editable = ("is_active",)

    @admin.display(description="apps")
    def app_list(self, obj: Any) -> str:
        return ", ".join(apps_of(obj.pk)) or "-"

    def save_model(
        self, request: HttpRequest, obj: Any, form: forms.ModelForm, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        # The list's Active column saves a form without the apps.
        if "apps" in form.cleaned_data:
            set_apps(obj.pk, form.cleaned_data["apps"])
