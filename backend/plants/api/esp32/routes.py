import json
import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from plants.api.esp32.devices import device_for_key
from plants.api.esp32.serializers import HumidityDataSerializer
from plants.api.esp32.service import fetch_weather_data
from plants.models import Esp32Data

logger = logging.getLogger(__name__)

INVALID_KEY = {"error": "Missing or invalid device key."}


@method_decorator(csrf_exempt, name="dispatch")
class Esp32Api(View):
    async def post(self, request: Any, *args: Any, **kwargs: Any) -> JsonResponse:
        logger.info("Receiving data from ESP32, starting data treatment")

        device = await sync_to_async(device_for_key)(
            request.headers.get("X-Device-Key", "")
        )
        if device is None:
            return JsonResponse(INVALID_KEY, status=401)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        serializer = HumidityDataSerializer(data=body)

        if not serializer.is_valid():
            logger.error("Invalid data received from ESP32: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=400)

        # validated_data uses each field's source, not the JSON name.
        analog_value = serializer.validated_data["analog_value"]
        digital_value = serializer.validated_data["digital_value"]

        logger.info("Fetching weather data")
        weather_data = await fetch_weather_data(user_id=device.user_id)

        # The soil reading is the plant's own data: a failure on OpenWeather's side
        # mustn't lose it, so it is saved without the weather.
        if weather_data.error_message:
            logger.warning(
                "Saving a reading of device %s without the weather: %s",
                device.pk,
                weather_data.error_message,
            )

        logger.info("Creating data on the database")

        await Esp32Data.objects.acreate(
            analog_value=analog_value,
            digital_value=digital_value,
            temperature=weather_data.temperature,
            humidity=weather_data.humidity,
            device=device,
            user_id=device.user_id,
        )

        logger.info("Data created successfully")
        return JsonResponse({}, status=200)

    async def get(self, request: Any, *args: Any, **kwargs: Any) -> JsonResponse:
        logger.info("Fetching humidity data from ESP32")

        device = await sync_to_async(device_for_key)(
            request.headers.get("X-Device-Key", "")
        )
        if device is None:
            return JsonResponse(INVALID_KEY, status=401)

        readings = Esp32Data.objects.filter(device=device).order_by("id")
        data = [entry async for entry in readings]

        if not data:
            logger.info("No humidity data found in database")
            return JsonResponse({"error": "No data found"}, status=404)

        serializer = HumidityDataSerializer(data, many=True)
        return JsonResponse(serializer.data, safe=False, status=200)
