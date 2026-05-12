from typing import Any

from rest_framework import serializers


class HumidityDataSerializer(serializers.Serializer[Any]):
    analogValue = serializers.IntegerField(source="analog_value")
    digitalValue = serializers.IntegerField(source="digital_value")
    userId = serializers.IntegerField(source="user_id")