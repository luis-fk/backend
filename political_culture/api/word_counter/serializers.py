from rest_framework import serializers


class ContentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    content = serializers.FileField()
