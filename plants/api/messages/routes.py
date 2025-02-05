import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.messages.serializers import ChatHistorySerializer
from plants.models import ChatHistory

logger = logging.getLogger(__name__)


class MessagesApi(APIView):
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get("userId")
        
        logger.info(f"Fetching chat history for user {user_id}")
        
        messages = ChatHistory.objects.filter(user_id=user_id).order_by("id").all()

        if messages:
            serializer = ChatHistorySerializer(messages, many=True)
            
            logger.info(f"Chat history fetched successfully for user {user_id}")
            
            return Response(serializer.data, status=200)
        else:
            logger.info("No messages found for user")
            
            return Response({"message": "No messages found for user"}, status=204)
