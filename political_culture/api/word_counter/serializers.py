from rest_framework import serializers


class TextsSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    text = serializers.CharField()
