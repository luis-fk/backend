from typing import Any

from rest_framework import serializers


class MessageSerializer(serializers.Serializer[Any]):
    user_id = serializers.IntegerField()
    message = serializers.CharField(max_length=1000)