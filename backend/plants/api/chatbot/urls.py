from django.urls import path

from plants.api.chatbot.routes import ChatBotApi

chatbot_urls = [
    path("api/chatbot/message", ChatBotApi.as_view(), name="message"),
]
