from typing import Any

from rest_framework import serializers


class ClassRoomSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
