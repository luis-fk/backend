import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.esp32.serializers import HumidityDataSerializer
from plants.api.esp32.service import fetch_weather_data
from plants.models import Esp32Data

logger = logging.getLogger(__name__)


class Esp32Api(APIView):
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving data from ESP32, starting data treatment")

        serializer = HumidityDataSerializer(data=request.data)

        if serializer.is_valid():
            analog_value = serializer.validated_data["analogValue"]
            digital_value = serializer.validated_data["digitalValue"]
            user_id = serializer.validated_data["userId"]

            logger.info("Fechting weather data")
            weather_data = fetch_weather_data(user_id=user_id)

            if weather_data.error_message:
                logger.error("Error fetching weather data1")
                return Response(status=400)

            temperature = weather_data.temperature
            humidity = weather_data.humidity

            logger.info("Creating data on the database")

            Esp32Data.objects.create(
                analog_value=analog_value,
                digital_value=digital_value,
                temperature=temperature,
                humidity=humidity,
                user_id=user_id,
            )

            logger.info("Data created successfully")

            return Response(status=200)
        else:
            logger.error("Invalid data received from ESP32", serializer.errors)

            return Response(serializer.errors, status=400)

    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Fetching humidity data from ESP32")

        data = Esp32Data.objects.all()

        if not data:
            logger.info("No humidity data found in database")
            return Response({"error": "No data found"}, status=404)

        serializer = HumidityDataSerializer(data, many=True)
        return Response(serializer.data, status=200)
