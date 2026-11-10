import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api_auth import require_same_user, require_user_token
from political_culture.api.chatbot.chatbot import LLM
from political_culture.api.chatbot.help import first_message
from political_culture.api.chatbot.serializers import HelpSerializer, MessageSerializer
from political_culture.api.chatbot.utils import clean_html

logger = logging.getLogger(__name__)


class ChatBotApi(APIView):
    llm = LLM()

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving message from user to be processed by LLM")

        token_user_id = require_user_token(request, "political-culture")
        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            text = serializer.validated_data["text"]
            require_same_user(token_user_id, user_id)

            logger.info(f"Processing user text {text} for user {user_id}")

            cleaned_text = clean_html(text)

            self.llm.process_text(
                text=cleaned_text,
                user_id=int(user_id),
                language=serializer.validated_data["language"],
            )

            return Response(
                {"user_id": user_id, "response": "accepted"},
                status=status.HTTP_200_OK,
            )
        else:
            logger.error("Error processing user text")

            return Response({"error": "Invalid request data"}, status=400)


class ChatHelpApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        require_user_token(request, "political-culture")
        serializer = HelpSerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response({"error": "Invalid request data"}, status=400)

        return Response(
            {"message": first_message(serializer.validated_data["language"])},
            status=status.HTTP_200_OK,
        )
