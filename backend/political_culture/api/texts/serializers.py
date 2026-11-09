from typing import Any

from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

# Whole books fit.
MAX_PDF_BYTES = 100 * 1024 * 1024
# A PDF may have a few bytes before its header.
PDF_HEADER_SEARCH = 1024


class UploadSerializer(serializers.Serializer[Any]):
    content = serializers.FileField()

    def validate_content(self, content: UploadedFile) -> UploadedFile:
        if content.size is None or content.size > MAX_PDF_BYTES:
            raise serializers.ValidationError("The PDF is larger than 100 MB.")
        content.seek(0)
        start = content.read(PDF_HEADER_SEARCH)
        content.seek(0)
        if b"%PDF-" not in start:
            raise serializers.ValidationError("The file is not a PDF.")
        return content


class SelectionSerializer(serializers.Serializer[Any]):
    selected = serializers.BooleanField()
