import logging
from typing import Any

from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api_auth import require_user_token
from political_culture.api.texts.serializers import (
    SelectionSerializer,
    UploadSerializer,
)
from political_culture.api.texts.service import (
    DuplicateText,
    library_texts,
    select_text,
    start_upload,
)
from political_culture.models import Texts

logger = logging.getLogger(__name__)


class TextsApi(APIView):
    """The shared library. Any user lists it and adds PDFs; only the Django admin
    edits or deletes a text, since a delete would remove it for everyone."""

    parser_classes = [MultiPartParser]

    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        user_id = require_user_token(request, "political-culture")
        return Response(library_texts(int(user_id)))

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        user_id = require_user_token(request, "political-culture")
        serializer = UploadSerializer(data=request.data)

        if not serializer.is_valid():
            logger.info(f"Upload refused: {serializer.errors}")
            error = (
                "Send a PDF of up to 100 MB."
                if "content" in serializer.errors
                else "Send an upload_id, a UUID that the result will carry."
            )
            return Response({"error": error}, status=400)

        pdf = serializer.validated_data["content"]
        upload_id = str(serializer.validated_data["upload_id"])
        try:
            start_upload(pdf, int(user_id), upload_id)
        except DuplicateText:
            return Response(
                {"error": "This PDF is already in the library, or being read."},
                status=409,
            )

        logger.info(f"Reading {pdf.name} for user {user_id} (upload {upload_id})")
        return Response({"upload_id": upload_id}, status=202)


class TextSelectionApi(APIView):
    """Ticks or unticks a library text for the analyses of the token's user."""

    def put(self, request: Any, text_id: int) -> Response:
        user_id = require_user_token(request, "political-culture")
        serializer = SelectionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({"error": "Send selected as true or false."}, status=400)

        try:
            select_text(int(user_id), text_id, serializer.validated_data["selected"])
        except Texts.DoesNotExist:
            return Response({"error": "Text not found."}, status=404)

        return Response(status=204)
