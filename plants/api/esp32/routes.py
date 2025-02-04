import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from plants.api.esp32.serializers import HumidityDataSerializer
from plants.api.esp32.service import fetch_weather_data
from plants.models import Esp32Data

logger = logging.getLogger(__name__)


class Esp32Api(APIView):
    def post(self, request, *args, **kwargs):
        logger.info("Receiving data from ESP32, starting data treatment")
        serializer = HumidityDataSerializer(data=request.data)

        if serializer.is_valid():
            analog_value = serializer.validated_data["analogValue"]
            digital_value = serializer.validated_data["digitalValue"]

            logger.info("Fechting weather data")
            weather_data = fetch_weather_data()

            if "error" in weather_data:
                logger.error("Error fetching weather data")
                return Response(status=400)

            temperature = weather_data["temperature"]
            humidity = weather_data["humidity"]

            logger.info("Creating data on the database")

            Esp32Data.objects.create(
                analog_value=analog_value,
                digital_value=digital_value,
                temperature=temperature,
                humidity=humidity,
            )

            logger.info("Data created successfully")

            return Response(status=200)
        else:
            logger.error("Invalid data received from ESP32", serializer.errors)

            return Response(serializer.errors, status=400)

    def get(self, request, *args, **kwargs):
        logger.info("Fetching humidity data from ESP32")

        data = Esp32Data.objects.all()

        if not data:
            logger.info("No humidity data found in database")
            return Response({"error": "No data found"}, status=404)

        serializer = HumidityDataSerializer(data, many=True)
        return Response(serializer.data, status=200)
