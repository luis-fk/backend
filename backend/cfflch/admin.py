from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.http import HttpRequest

from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom, Users


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


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "name_normalized"]
    search_fields = ["name"]


class AdmissionPDFInline(admin.TabularInline):
    model = AdmissionPDF
    extra = 0
    fields = ["url", "search_title"]


@admin.register(AdmissionResult)
class AdmissionResultAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "student_name",
        "year",
        "approved",
        "class_room",
        "created_at",
    ]
    list_filter = ["year", "approved", "class_room"]
    search_fields = ["student_name"]
    date_hierarchy = "created_at"
    inlines = [AdmissionPDFInline]


@admin.register(AdmissionPDF)
class AdmissionPDFAdmin(admin.ModelAdmin):
    list_display = ["id", "result", "search_title", "url"]
    search_fields = ["search_title", "url"]
    raw_id_fields = ["result"]
