from rest_framework import serializers


class HumidityDataSerializer(serializers.Serializer):
    analogValue = serializers.IntegerField()
    digitalValue = serializers.IntegerField()
    userId = serializers.IntegerField()
