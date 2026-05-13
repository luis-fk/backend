from typing import Any

from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer[Any]):
    class Meta:
        model = User
        fields = ["id", "username"]
