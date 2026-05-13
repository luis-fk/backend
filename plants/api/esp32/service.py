import logging
from typing import Optional

import httpx
from django.conf import settings
from pydantic import Field

from plants.api.config.schemas import InfoSchema
from plants.models import Users


class WeatherDataSchema(InfoSchema):
    temperature: Optional[float] = Field(
        None, description="Temperature value from the ESP32"
    )
    humidity: Optional[float] = Field(None, description="Humidity value from the ESP32")


async def fetch_weather_data(user_id: int) -> WeatherDataSchema:
    logging.info("Fetching weather data")

    user = await Users.objects.filter(id=user_id).afirst()

    if user is None:
        logging.error("User not found")
        return WeatherDataSchema(error_message="User not found")

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={user.latitude}&lon={user.longitude}&units=metric&appid={settings.OPEN_WEATHER_API_KEY}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 200:
        logging.info("Sending weather data to be stored on the database")

        data = response.json()

        temp = round(data["main"]["temp"])
        humidity = data["main"]["humidity"]

        return WeatherDataSchema(temperature=temp, humidity=humidity)
    else:
        logging.error("Error fetching weather data")

        return WeatherDataSchema(error_message="Error fetching weather data")
