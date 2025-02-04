import logging

import requests
from environ import Env
from pydantic import BaseModel

env = Env()
Env.read_env()


class weatherData(BaseModel):
    temperature: float
    humidity: float


def fetch_weather_data() -> weatherData:
    logging.info("Fetching weather data")

    url = f"https://api.openweathermap.org/data/2.5/weather?lat=-29.46&lon=-51.96&units=metric&appid={env('OPEN_WEATHER_API_KEY')}"
    response = requests.get(url)

    if response.status_code == 200:
        logging.info("Sending weather data to be stored on the database")

        data = response.json()
        
        temp = round(data["main"]["temp"])
        humidity = data["main"]["humidity"]

        return {"temperature": temp, "humidity": humidity}
    else:
        logging.error("Error fetching weather data")

        return {"error": "Error fetching weather data"}
