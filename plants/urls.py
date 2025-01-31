from django.contrib import admin
from django.urls import path

from plants.api.messages.urls import messages_urls
from plants.api.users.urls import users_urls

urlpatterns = [path("admin/", admin.site.urls),] + messages_urls + users_urls
