from django.urls import path

from plants.api.esp32.routes import Esp32Api

esp32_urls = [
    path("api/esp32/humidity-data", Esp32Api.as_view(), name="humidity-data"),
]
