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


WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_weather_data(user_id: int) -> WeatherDataSchema:
    logging.info("Fetching weather data")

    user = await Users.objects.filter(id=user_id).afirst()

    if user is None:
        logging.error("User not found")
        return WeatherDataSchema(error_message="User not found")

    if not user.latitude or not user.longitude:
        return WeatherDataSchema(error_message="The owner has no location")

    # As params, httpx encodes the location, whatever was typed in the admin.
    params = {
        "lat": user.latitude,
        "lon": user.longitude,
        "units": "metric",
        "appid": settings.OPEN_WEATHER_API_KEY,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(WEATHER_URL, params=params)
    except httpx.HTTPError as error:
        return WeatherDataSchema(error_message=f"OpenWeather didn't answer: {error!r}")

    if response.status_code != 200:
        logging.error("Error fetching weather data")
        return WeatherDataSchema(error_message="Error fetching weather data")

    try:
        data = response.json()
        temperature = round(data["main"]["temp"])
        humidity = data["main"]["humidity"]
    except (KeyError, TypeError, ValueError) as error:
        return WeatherDataSchema(
            error_message=f"OpenWeather's answer has no weather: {error!r}"
        )

    logging.info("Sending weather data to be stored on the database")
    return WeatherDataSchema(temperature=temperature, humidity=humidity)
