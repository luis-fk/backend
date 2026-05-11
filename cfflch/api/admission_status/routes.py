import asyncio
import logging

import httpx
from channels.layers import get_channel_layer
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from cfflch.api.admission_status.serializers import AdmissionStatusRequestSerializer
from cfflch.api.admission_status.service import AdmissionStatusService

logger = logging.getLogger(__name__)


class AdmissionStatusApi(APIView):
    async def post(self, request: Request) -> Response:
        serializer = AdmissionStatusRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        student_names = serializer.validated_data["names"]
        year = serializer.validated_data["year"]
        request_id = serializer.validated_data["request_id"]

        task = asyncio.ensure_future(
            self._process_admission_task(student_names, year, request_id)
        )
        task.add_done_callback(
            lambda t: logger.error(f"Admission task failed: {t.exception()}")
            if not t.cancelled() and t.exception()
            else None
        )

        return Response(
            {"message": "Processing started", "request_id": request_id},
            status=status.HTTP_202_ACCEPTED,
        )

    async def _process_admission_task(
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