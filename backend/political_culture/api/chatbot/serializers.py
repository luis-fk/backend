from typing import Any

from rest_framework import serializers

from political_culture.api.chatbot.help import DEFAULT_LANGUAGE, LANGUAGES


class MessageSerializer(serializers.Serializer[Any]):
    user_id = serializers.IntegerField()
    text = serializers.CharField()
    language = serializers.ChoiceField(choices=LANGUAGES, default=DEFAULT_LANGUAGE)
