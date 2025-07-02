# serializers.py
from rest_framework import serializers


class NameListSerializer(serializers.Serializer):
    names = serializers.ListField(
        child=serializers.CharField(),
    )
