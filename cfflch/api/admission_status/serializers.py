from typing import Any

from rest_framework import serializers


class AdmissionStatusRequestSerializer(serializers.Serializer[Any]):
    names = serializers.ListField(
        child=serializers.CharField(),
    )
    year = serializers.IntegerField()
    request_id = serializers.CharField()
    class_name = serializers.CharField(required=False, allow_null=True, default=None)
