from typing import Any

from rest_framework import serializers


class AdmissionResultSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    student_name = serializers.CharField()
    year = serializers.IntegerField()
    approved = serializers.BooleanField()
    class_room_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    pdf_urls = serializers.SerializerMethodField()

    def get_pdf_urls(self, obj: Any) -> list[dict[str, str]]:
        return [{"url": p.url, "search_title": p.search_title} for p in obj.pdfs.all()]


class AdmissionResultPatchSerializer(serializers.Serializer[Any]):
    approved = serializers.BooleanField(required=False)
    class_room_id = serializers.IntegerField(required=False, allow_null=True)
