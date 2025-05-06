from django.urls import path

from political_culture.api.chatbot.routes import ChatBotApi
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


political_culture_urls = chatbot_urls + word_counter_urls