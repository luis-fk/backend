from django.urls import path

from plants.api.messages.routes import MessagesApi

messages_urls = [
    path("api/chat-history/<str:userId>/", MessagesApi.as_view(), name="message"),
]
