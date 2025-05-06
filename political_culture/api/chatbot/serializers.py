from rest_framework import serializers


class MessageSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    text = serializers.CharField(max_length=1000)
