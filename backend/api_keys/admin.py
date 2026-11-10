from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from api_keys.app_users import USERS_MODELS, add_to_apps, apps_of, users_model
from api_keys.models import ApiKey


class ApiKeyForm(forms.ModelForm):
    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        app = cleaned_data.get("app")
        user_id = cleaned_data.get("user_id")
        # Only the add form has these fields.
        if app and user_id is not None:
            users = users_model(app)
            if not users.objects.filter(pk=user_id).exists():
                self.add_error("user_id", f"{app} has no user with id {user_id}.")
        return cleaned_data


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    form = ApiKeyForm
    list_display = [
        "name",
        "app",
        "user_id",
        "prefix",
        "active",
        "created_at",
        "last_used_at",
    ]
    list_editable = ["active"]
    list_filter = ["app", "active"]

    def get_fields(self, request: HttpRequest, obj: ApiKey | None = None) -> list[str]:
        if obj is None:
            return ["name", "app", "user_id"]
        return [
            "name",
            "app",
            "user_id",
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
        return ["app", "user_id", "prefix", "created_at", "last_used_at"]

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


def apps_field(help_text: str) -> forms.MultipleChoiceField:
    return forms.MultipleChoiceField(
        choices=[(app, app) for app in USERS_MODELS],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=help_text,
    )


class UserCreationWithAppsForm(AdminUserCreationForm):
    apps = apps_field("The apps the person can sign in to.")


class UserChangeWithAppsForm(UserChangeForm):
    apps = apps_field(
        "Ticking an app adds the person to it. Unticking doesn't remove them: that "
        "would delete their data in the app, so it is done in the app's Users "
        "table, which lists what goes with it."
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["apps"].initial = apps_of(self.instance.pk)


# The admin's user pages, with the apps each person is in: Django's own, which
# the auth app registers first, plus an apps field.
User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class UserWithAppsAdmin(UserAdmin):
    add_form = UserCreationWithAppsForm
    form = UserChangeWithAppsForm
    add_fieldsets = (*UserAdmin.add_fieldsets, ("Apps", {"fields": ("apps",)}))
    fieldsets = (*(UserAdmin.fieldsets or ()), ("Apps", {"fields": ("apps",)}))
    list_display = (*UserAdmin.list_display, "app_list")

    @admin.display(description="apps")
    def app_list(self, obj: Any) -> str:
        return ", ".join(apps_of(obj.pk)) or "-"

    def save_model(
        self, request: HttpRequest, obj: Any, form: forms.ModelForm, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        add_to_apps(obj.pk, form.cleaned_data.get("apps", []))
