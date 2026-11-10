from django.urls import path

from political_culture.api.chatbot.routes import ChatBotApi, ChatHelpApi
from political_culture.api.messages.routes import MessagesApi
from political_culture.api.texts.routes import TextsApi, TextSelectionApi
from political_culture.api.users.routes import UserApi

chatbot_urls = [
    path("api/political-culture/chatbot/message", ChatBotApi.as_view(), name="message"),
    path("api/political-culture/chatbot/help", ChatHelpApi.as_view(), name="chat_help"),
]

texts_urls = [
    path("api/political-culture/texts", TextsApi.as_view(), name="texts"),
    path(
        "api/political-culture/texts/<int:text_id>/selection",
        TextSelectionApi.as_view(),
        name="text_selection",
    ),
]

messages_urls = [
    path(
        "api/political-culture/chat-history/<str:userId>",
        MessagesApi.as_view(),
        name="message",
    ),
]

users_urls = [
    path(
        "api/political-culture/users/<str:name>",
        UserApi.as_view(),
        name="political_culture_user",
    ),
]

political_culture_urls = chatbot_urls + texts_urls + messages_urls + users_urls
