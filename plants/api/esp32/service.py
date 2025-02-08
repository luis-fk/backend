import logging
from typing import Optional

import requests
from environ import Env
from pydantic import Field

from plants.api.config.schemas import InfoSchema
from plants.models import Users

env = Env()
Env.read_env()


class WeatherDataSchema(InfoSchema):
    temperature: Optional[float] = Field(
        None, description="Temperature valeu from the ESP32"
    )
    humidity: Optional[float] = Field(None, description="Humidity value from the ESP32")


def fetch_weather_data(user_id: int) -> WeatherDataSchema:
    logging.info("Fetching weather data")

    user = Users.objects.filter(id=user_id).first()

    if user is None:
        logging.error("User not found")

        return WeatherDataSchema(error_message="User not found")

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={user.latitude}&lon={user.longitude}&units=metric&appid={env('OPEN_WEATHER_API_KEY')}"

    response = requests.get(url)

    if response.status_code == 200:
        logging.info("Sending weather data to be stored on the database")

        data = response.json()

        temp = round(data["main"]["temp"])
        humidity = data["main"]["humidity"]

        return WeatherDataSchema(temperature=temp, humidity=humidity)
    else:
        logging.error("Error fetching weather data")

        return WeatherDataSchema(error_message="Error fetching weather data")
