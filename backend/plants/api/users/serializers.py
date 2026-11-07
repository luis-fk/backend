from typing import Any

from rest_framework import serializers

from plants.models import Users


class UserSerializer(serializers.ModelSerializer[Any]):
    class Meta:
        model = Users
        fields = ["id"]
