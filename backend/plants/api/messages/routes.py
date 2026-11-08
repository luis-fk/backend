import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api_auth import require_same_user, require_user_token
from plants.api.messages.serializers import ChatHistorySerializer
from plants.models import ChatHistory

logger = logging.getLogger(__name__)


class MessagesApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        token_user_id = require_user_token(request, "plants")
        user_id = kwargs.get("userId")
        require_same_user(token_user_id, user_id)

        logger.info(f"Fetching chat history for user {user_id}")

        messages = ChatHistory.objects.filter(user_id=user_id).order_by("id").all()

        serializer = ChatHistorySerializer(messages, many=True)

        logger.info(f"Chat history fetched successfully for user {user_id}")

        return Response(serializer.data, status=200)
