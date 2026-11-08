from typing import Any

from django import forms
from django.apps import apps
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from api_keys.models import ApiKey

# Looked up by name, so this app doesn't import the others.
USERS_MODELS = {
    "plants": "plants.Users",
    "political-culture": "political_culture.Users",
    "cfflch": "cfflch.Users",
}


class ApiKeyForm(forms.ModelForm):
    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        app = cleaned_data.get("app")
        user_id = cleaned_data.get("user_id")
        # Only the add form has these fields.
        if app and user_id is not None:
            users = apps.get_model(USERS_MODELS[app])
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
