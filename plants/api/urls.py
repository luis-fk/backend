from django.urls import path

from .messages.routes import MessageView

api_urls = [
    path("api/message/", MessageView.as_view(), name="message"),
]
