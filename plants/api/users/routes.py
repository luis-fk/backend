import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.users.serializers import UserSerializer
from plants.models import Users

logger = logging.getLogger(__name__)


class UserApi(APIView):
    def get(self, request, *args, **kwargs):
        name = kwargs.get("name")
        
        logger.info(f"Fetching user info for {name}")
        
        user = Users.objects.filter(username=name).first()

        if user:
            serializer = UserSerializer(user)
            
            logger.info(f"User info fetched successfully for {name}")
            
            return Response(serializer.data)
        else:
            logger.info(f"User {user} not found")
            
            return Response({"error": "User not found"}, status=404)
