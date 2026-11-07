from typing import Any

from rest_framework import serializers

from plants.models import ChatHistory


class ChatHistorySerializer(serializers.ModelSerializer[Any]):
    class Meta:
        model = ChatHistory
        fields = ["role", "message"]
