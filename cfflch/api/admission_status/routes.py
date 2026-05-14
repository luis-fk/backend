import asyncio
import json
import logging
from typing import Any

import httpx
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from cfflch.api.admission_status.schemas import StudentResult
from cfflch.api.admission_status.serializers import AdmissionStatusRequestSerializer
from cfflch.api.admission_status.service import AdmissionStatusService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AdmissionStatusApi(View):
    async def post(self, request: Any) -> JsonResponse:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AdmissionStatusRequestSerializer(data=body)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": "Invalid request data"}, status=status.HTTP_400_BAD_REQUEST
            )

        student_names = serializer.validated_data["names"]
        year = serializer.validated_data["year"]
        request_id = serializer.validated_data["request_id"]
        class_name = serializer.validated_data["class_name"]

        task = asyncio.ensure_future(
            self._process_admission_task(student_names, year, request_id, class_name)
        )
        task.add_done_callback(
            lambda t: (
                logger.error(f"Admission task failed: {t.exception()}")
                if not t.cancelled() and t.exception()
                else None
            )
        )

        return JsonResponse(
            {"message": "Processing started", "request_id": request_id},
            status=status.HTTP_202_ACCEPTED,
        )

    async def _process_admission_task(
        self,
        student_names: list[str],
        year: int,
        request_id: str,
        class_name: str | None,
    ) -> None:
        channel_layer = get_channel_layer()

        async def on_student_done(entries: list[StudentResult]) -> None:
            if channel_layer:
                await channel_layer.group_send(
                    f"admission_status_{request_id}",
                    {
                        "type": "admission_status.message",
                        "message": [e.model_dump() for e in entries],
                    },
                )

        try:
            async with httpx.AsyncClient() as client:
                service = AdmissionStatusService(http_client=client)
                await service.check_admission_status(
                    student_names, year, class_name, on_student_done
                )
        except Exception as e:
            logger.error(f"Error processing admission status: {e}")

        if channel_layer:
            await channel_layer.group_send(
                f"admission_status_{request_id}",
                {"type": "admission_status.done"},
            )
