# serializers.py
from rest_framework import serializers


class AdmissionStatusRequestSerializer(serializers.Serializer):
    names = serializers.ListField(
        child=serializers.CharField(),
    )
    year = serializers.IntegerField()
    request_id = serializers.CharField()
