from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import logging

from plants.api.chatbot.chatbot import LLM
from plants.api.chatbot.serializers import MessageSerializer

logger = logging.getLogger(__name__)

class ChatBotApi(APIView):
    llm = LLM()
    llm.setup()

    def post(self, request, *args, **kwargs):
        logger.info("Receiving message from user to be processed by LLM")
        
        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            message = serializer.validated_data["message"]
            
            logger.info(f"Processing user message {message} for user {user_id}")
            
            response = self.llm.process_message(message=message, user_id=user_id)
            return Response(
                {"user_id": user_id, "message": message, "response": response},
                status=status.HTTP_200_OK,
            )
        else:
            logger.error("Error processing user message")
            
            return Response(serializer.errors, status=400)
