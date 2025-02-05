from plants.models import Users
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ["id", "username"]
