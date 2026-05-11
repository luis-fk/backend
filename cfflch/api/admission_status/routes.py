import asyncio
import json
import logging

import httpx
from channels.layers import get_channel_layer
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from cfflch.api.admission_status.serializers import AdmissionStatusRequestSerializer
from cfflch.api.admission_status.service import AdmissionStatusService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AdmissionStatusApi(View):
    async def post(self, request: HttpRequest) -> JsonResponse:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        serializer = AdmissionStatusRequestSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        student_names = serializer.validated_data["names"]
        year = serializer.validated_data["year"]
        request_id = serializer.validated_data["request_id"]

        asyncio.create_task(
            self.process_admission_task(student_names, year, request_id)
        )

        return JsonResponse(
            {"message": "Processing started", "request_id": request_id},
            status=status.HTTP_202_ACCEPTED,
        )

    async def process_admission_task(
        self, student_names: list[str], year: int, request_id: str
    ) -> None:
        try:
            async with httpx.AsyncClient() as client:
                service = AdmissionStatusService(http_client=client)
                results = await service.check_admission_status(student_names, year)

                channel_layer = get_channel_layer()
                if channel_layer:
                    await channel_layer.group_send(
                        f"admission_status_{request_id}",
                        {"type": "admission_status.message", "message": results},
                    )
        except Exception as e:
            logger.error(f"Error processing admission status: {e}")
