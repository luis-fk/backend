from rest_framework import serializers

from plants.models import Esp32Data


class HumidityDataSerializer(serializers.Serializer):
    analogValue = serializers.IntegerField()
    digitalValue = serializers.IntegerField()
    userId = serializers.IntegerField()
    
class Esp32DataSerializer(serializers.Serializer):
    class Meta:
        model = Esp32Data
        fields = ['analog_value', 'digital_value']
        read_only_fields = ['created_at', 'temperature', 'humidity']
