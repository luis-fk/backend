import logging
from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.users.serializers import UserSerializer

logger = logging.getLogger(__name__)


class UserApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        name = kwargs.get("name")

        logger.info(f"Fetching user info for {name}")

        User = get_user_model()
        try:
            auth_user = User.objects.using("default").get(username=name)
        except User.DoesNotExist:
            logger.info(f"User {name} not found")
            return Response({"error": "User not found."}, status=404)

        serializer = UserSerializer(auth_user)

        logger.info(f"User info fetched successfully for {name}")

        return Response(serializer.data)
