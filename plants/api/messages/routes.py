from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.messages.serializers import ChatHistorySerializer
from plants.models import ChatHistory


class MessagesApi(APIView):
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get("userId")
        messages = ChatHistory.objects.filter(user_id=user_id).order_by("id").all()
        
        if messages:
            serializer = ChatHistorySerializer(messages, many=True)
            return Response(serializer.data, status=200)
        else:
            return Response({"message": "No messages found for user"}, status=204)
