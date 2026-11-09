from django.urls import path

from political_culture.api.texts import consumers

websocket_urlpatterns = [
    path("ws/political-culture/texts/<str:userId>", consumers.TextsConsumer.as_asgi()),
]
