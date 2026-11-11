from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api_auth import require_user_token
from plants.api.sensors.service import (
    ALLOWED_HOURS,
    device_of,
    devices_of,
    readings_of,
)


class DevicesApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        user_id = int(require_user_token(request, "plants"))
        return Response(devices_of(user_id))


class ReadingsApi(APIView):
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        user_id = int(require_user_token(request, "plants"))
        # Compared as text: isdigit() lets through digits that int() refuses.
        hours = request.query_params.get("hours", "")
        if hours not in {str(allowed) for allowed in ALLOWED_HOURS}:
            return Response({"error": "hours must be 24, 168 or 720."}, status=400)

        device = device_of(user_id, kwargs["device_id"])
        if device is None:
            return Response({"error": "Device not found."}, status=404)

        since = timezone.now() - timedelta(hours=int(hours))
        return Response({"readings": readings_of(device, since)})
