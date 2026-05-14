from django.contrib import admin

from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom, Users


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ["id", "auth_user_id"]
    search_fields = ["auth_user_id"]


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
