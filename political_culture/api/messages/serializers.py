from typing import Any

from rest_framework import serializers

from political_culture.models import ChatHistory


class ChatHistorySerializer(serializers.ModelSerializer[Any]):
    class Meta:
        model = ChatHistory
        fields = ["role", "message"]
