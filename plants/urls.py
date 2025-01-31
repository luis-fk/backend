from django.contrib import admin
from django.urls import path

from .api.urls import api_urls

urlpatterns = [path("admin/", admin.site.urls),] + api_urls
