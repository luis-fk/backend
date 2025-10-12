from django.urls import path

from political_culture.api.messages import consumers

websocket_urlpatterns = [
    path("ws/chat/<str:userId>", consumers.ChatConsumer.as_asgi()),
]
