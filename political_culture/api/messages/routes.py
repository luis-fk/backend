import json
import logging
import time
from typing import Any

from django.db import close_old_connections
from django.http import HttpRequest, StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from political_culture.api.messages.serializers import ChatHistorySerializer
from political_culture.models import ChatHistory

logger = logging.getLogger(__name__)


class MessagesApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        user_id = kwargs.get("userId")

        logger.info(f"Fetching chat history for user {user_id}")

        messages = ChatHistory.objects.filter(user_id=user_id).order_by("id")

        if messages:
            serializer = ChatHistorySerializer(messages, many=True)

            logger.info(f"Chat history fetched successfully for user {user_id}")

            return Response(serializer.data, status=200)
        else:
            logger.info("No messages found for user")

            return Response({"message": "No messages found for user"}, status=204)


def chat_stream(request: HttpRequest, userId: int) -> StreamingHttpResponse:
    def event_stream():
        close_old_connections()

        last_id = (
            ChatHistory.objects.filter(user_id=userId, role="ai")
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
            or 0
        )

        while True:
            new_ai_message = (
                ChatHistory.objects
                .filter(user_id=userId, role="ai", id__gt=last_id)
                .order_by("id")
            )
            if new_ai_message.exists():
                message = new_ai_message.last()
                payload = {"message": message.message, "role": message.role}
                yield f"data: {json.dumps(payload)}\n\n"
                last_id = message.id

            time.sleep(10)

    resp = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
