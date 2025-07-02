from django.urls import path

from political_culture.api.chatbot.routes import ChatBotApi
from political_culture.api.messages.routes import MessagesApi
from political_culture.api.word_counter.routes import WordCounterApi

chatbot_urls = [
    path("api/political-culture/chatbot/message", ChatBotApi.as_view(), name="message"),
]

word_counter_urls = [
    path(
        "api/political-culture/word-counter",
        WordCounterApi.as_view(),
        name="word_counter",
    ),
]

messages_urls = [
    path(
        "api/political-culture/chat-history/<str:userId>",
        MessagesApi.as_view(),
        name="message",
    ),
]

political_culture_urls = chatbot_urls + word_counter_urls + messages_urls
