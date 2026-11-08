from django.http import JsonResponse
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.api_auth import require_user_token
from cfflch.api.class_rooms.serializers import ClassRoomSerializer
from cfflch.models import ClassRoom


class ClassRoomsListApi(APIView):
    def get(self, request: Request) -> JsonResponse:
        require_user_token(request, "cfflch")
        classrooms = ClassRoom.objects.all()
        serializer = ClassRoomSerializer(classrooms, many=True)
        return JsonResponse(serializer.data, safe=False)
