import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.chatbot.chatbot import LLM
from plants.api.chatbot.serializers import MessageSerializer

logger = logging.getLogger(__name__)


class ChatBotApi(APIView):
    llm = LLM()
    llm.setup()

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving message from user to be processed by LLM")

        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            message = serializer.validated_data["message"]

            logger.info(f"Processing user message {message} for user {user_id}")

            response = self.llm.process_message(message=message, user_id=int(user_id))

            if not response:
                logger.error("Error processing user message")
                return Response({"error": "Error processing user message"}, status=400)

            return Response(
                {"user_id": user_id, "response": response.data},
                status=status.HTTP_200_OK,
            )
        else:
            logger.error("Error processing user message")

            return Response(serializer.errors, status=400)
