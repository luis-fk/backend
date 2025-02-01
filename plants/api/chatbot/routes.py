from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.chatbot.chatbot import LLM
from plants.api.chatbot.serializers import MessageSerializer


class ChatBotApi(APIView):
    llm = LLM()
    llm.setup()

    def post(self, request, *args, **kwargs):
        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            message = serializer.validated_data["message"]

            response = self.llm.process_message(message=message, user_id=user_id)
            return Response(
                {"user_id": user_id, "message": message, "response": response},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=400)
