from django.urls import path

from plants.api.messages.routes import MessageApi

messages_urls = [
    path("api/message/", MessageApi.as_view(), name="message"),
]
