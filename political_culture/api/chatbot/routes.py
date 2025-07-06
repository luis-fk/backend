import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from political_culture.api.chatbot.chatbot import LLM
from political_culture.api.chatbot.serializers import MessageSerializer
from political_culture.api.chatbot.utils import clean_html

logger = logging.getLogger(__name__)


class ChatBotApi(APIView):
    llm = LLM()

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving message from user to be processed by LLM")

        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            text = serializer.validated_data["text"]

            logger.info(f"Processing user text {text} for user {user_id}")

            cleaned_text = clean_html(text)

            self.llm.process_text(text=cleaned_text, user_id=int(user_id))

            return Response(
                {"user_id": user_id, "response": "accepted"},
                status=status.HTTP_200_OK,
            )
        else:
            logger.error("Error processing user text")

            return Response(serializer.errors, status=400)
