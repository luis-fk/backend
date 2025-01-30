from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.messages.serializers import MessageSerializer
from plants.chatbot.chatbot import LLM


class MessageApi(APIView):
    def post(self, request, *args, **kwargs):
        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            message = serializer.validated_data["message"]

            llm = LLM()
            llm.setup()

            response = llm.process_message(message=message, user_id=user_id)
            return Response(
                {"user_id": user_id, "message": message, "response": response},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
