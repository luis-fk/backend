import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from political_culture.api.chatbot.chatbot import LLM
from political_culture.api.chatbot.serializers import MessageSerializer

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

            response = self.llm.process_text(text=text, user_id=int(user_id))

            if not response:
                logger.error("Error processing user text")
                return Response({"error": "Error processing user text"}, status=400)

            return Response(
                {"user_id": user_id, "response": response},
                status=status.HTTP_200_OK,
            )
        else:
            logger.error("Error processing user text")

            return Response(serializer.errors, status=400)
