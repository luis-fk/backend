import json
import logging
from typing import Any

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from plants.api.esp32.serializers import HumidityDataSerializer
from plants.api.esp32.service import fetch_weather_data
from plants.models import Esp32Data

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class Esp32Api(View):
    async def post(self, request: Any, *args: Any, **kwargs: Any) -> JsonResponse:
        logger.info("Receiving data from ESP32, starting data treatment")

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        serializer = HumidityDataSerializer(data=body)

        if not serializer.is_valid():
            logger.error("Invalid data received from ESP32: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=400)

        analog_value = serializer.validated_data["analogValue"]
        digital_value = serializer.validated_data["digitalValue"]
        user_id = serializer.validated_data["userId"]

        logger.info("Fetching weather data")
        weather_data = await fetch_weather_data(user_id=user_id)

        if weather_data.error_message:
            logger.error("Error fetching weather data")
            return JsonResponse({"error": weather_data.error_message}, status=400)

        logger.info("Creating data on the database")

        await Esp32Data.objects.acreate(
            analog_value=analog_value,
            digital_value=digital_value,
            temperature=weather_data.temperature,
            humidity=weather_data.humidity,
            user_id=user_id,
        )

        logger.info("Data created successfully")
        return JsonResponse({}, status=200)

    async def get(self, request: Any, *args: Any, **kwargs: Any) -> JsonResponse:
        logger.info("Fetching humidity data from ESP32")

        data = [entry async for entry in Esp32Data.objects.all()]

        if not data:
            logger.info("No humidity data found in database")
            return JsonResponse({"error": "No data found"}, status=404)

        serializer = HumidityDataSerializer(data, many=True)
        return JsonResponse(serializer.data, safe=False, status=200)
