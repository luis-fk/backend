from typing import Any

from rest_framework import serializers


class ContentSerializer(serializers.Serializer[Any]):
    user_id = serializers.IntegerField()
    content = serializers.FileField()