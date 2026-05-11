from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from cfflch.api.admission_status.serializers import NameListSerializer


class AdmissionStatusApi(APIView):
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        serializer = NameListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        names = serializer.validated_data["names"]

        return Response({"names_list": names}, status=status.HTTP_200_OK)
