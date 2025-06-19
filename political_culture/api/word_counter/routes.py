import logging
from typing import Any

from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from political_culture.api.word_counter.serializers import ContentSerializer
from political_culture.api.word_counter.service import add_text, add_text_word_count

logger = logging.getLogger(__name__)


class WordCounterApi(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving text, starting word counting")
        
        serializer = ContentSerializer(data=request.data)

        if serializer.is_valid():
            content = serializer.validated_data["content"]
            user_id = serializer.validated_data["user_id"]

            text_db = add_text(content, user_id, user_submitted_text=False)

            logger.info("Getting word frequency and total word count")

            add_text_word_count(text_db)

            logger.info("Data created successfully")

            return Response(status=200)
        else:
            logger.error("Invalid data received from ESP32", serializer.errors)

            return Response(serializer.errors, status=400)
