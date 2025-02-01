from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.users.serializers import UserSerializer
from plants.models import User


class UserApi(APIView):
    def get(self, request, *args, **kwargs):
        name = kwargs.get("name")
        user = User.objects.filter(username=name).first()

        if user:
            serializer = UserSerializer(user)
            return Response(serializer.data)
        else:
            return Response({"error": "User not found"}, status=404)
