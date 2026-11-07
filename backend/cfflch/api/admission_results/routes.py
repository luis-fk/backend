import logging
from typing import Any

from django.http import JsonResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView

from cfflch.api.admission_results.serializers import (
    AdmissionResultPatchSerializer,
    AdmissionResultSerializer,
)
from cfflch.models import AdmissionResult, ClassRoom

logger = logging.getLogger(__name__)


class AdmissionResultsListApi(APIView):
    def get(self, request: Request) -> JsonResponse:
        year_param = request.query_params.get("year")
        if not year_param:
            return JsonResponse(
                {"error": "year query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            year = int(year_param)
        except ValueError:
            return JsonResponse(
                {"error": "year must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = AdmissionResult.objects.filter(year=year).prefetch_related("pdfs")

        class_room_id_param = request.query_params.get("class_room_id")
        if class_room_id_param is not None:
            try:
                queryset = queryset.filter(class_room_id=int(class_room_id_param))
            except ValueError:
                return JsonResponse(
                    {"error": "class_room_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = AdmissionResultSerializer(queryset, many=True)
        return JsonResponse(serializer.data, safe=False)


class AdmissionResultDetailApi(APIView):
    def _get_object(self, pk: int) -> AdmissionResult | JsonResponse:
        try:
            return AdmissionResult.objects.prefetch_related("pdfs").get(pk=pk)
        except AdmissionResult.DoesNotExist:
            return JsonResponse(
                {"error": "Not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request: Request, pk: int) -> JsonResponse:
        result = self._get_object(pk)
        if isinstance(result, JsonResponse):
            return result

        serializer = AdmissionResultPatchSerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data: dict[str, Any] = serializer.validated_data

        if "approved" in data:
            result.approved = data["approved"]

        if "class_room_id" in data:
            class_room_id = data["class_room_id"]
            if class_room_id is None:
                result.class_room = None
            else:
                try:
                    result.class_room = ClassRoom.objects.get(pk=class_room_id)
                except ClassRoom.DoesNotExist:
                    return JsonResponse(
                        {"error": "ClassRoom not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

        result.save()
        return JsonResponse(
            AdmissionResultSerializer(result).data, status=status.HTTP_200_OK
        )

    def delete(self, request: Request, pk: int) -> JsonResponse:
        result = self._get_object(pk)
        if isinstance(result, JsonResponse):
            return result

        result.delete()
        return JsonResponse({}, status=status.HTTP_204_NO_CONTENT)
