from django.urls import path

from plants.api.sensors.routes import DevicesApi, ReadingsApi

sensors_urls = [
    path("api/plants/devices/", DevicesApi.as_view(), name="plants_devices"),
    path(
        "api/plants/devices/<int:device_id>/readings/",
        ReadingsApi.as_view(),
        name="plants_device_readings",
    ),
]
