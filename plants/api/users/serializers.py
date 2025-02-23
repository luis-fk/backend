from rest_framework import serializers

from plants.models import Users


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ["id", "username"]
