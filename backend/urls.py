from django.contrib import admin
from django.urls import path

from plants.api.messages.urls import messages_urls
from plants.api.users.urls import users_urls
from plants.api.chatbot.urls import chatbot_urls
from plants.api.esp32.urls import esp32_urls

urlpatterns = (
    [
        path("admin/", admin.site.urls),
    ]
    + chatbot_urls
    + users_urls
    + messages_urls
    + esp32_urls
)
