from django.urls import path

from political_culture.api.chatbot.routes import ChatBotApi

chatbot_urls = [
    path("api/chatbot/message", ChatBotApi.as_view(), name="message"),
]
