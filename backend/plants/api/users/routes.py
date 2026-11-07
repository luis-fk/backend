import logging
from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.users.serializers import UserSerializer
from plants.models import Users

logger = logging.getLogger(__name__)


class UserApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        name = kwargs.get("name")

        logger.info(f"Fetching user info for {name}")

        AuthUser = get_user_model()
        try:
            auth_user = AuthUser.objects.using("default").get(username=name)
        except AuthUser.DoesNotExist:
            logger.info(f"User {name} not found in auth DB")
            return Response({"error": "User not found."}, status=404)

        try:
            app_user = Users.objects.get(auth_user_id=auth_user.id)
        except Users.DoesNotExist:
            logger.info(f"User {name} not found in plants DB")
            return Response({"error": "User not found."}, status=404)

        serializer = UserSerializer(app_user)

        logger.info(f"User info fetched successfully for {name}")

        return Response(serializer.data)
