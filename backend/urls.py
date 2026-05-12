from django.contrib import admin
from django.urls import path

from cfflch.api.urls import cfflch_urls
from plants.api.urls import plants_urls
from political_culture.api.urls import political_culture_urls

urlpatterns = (
    [
        path("admin/", admin.site.urls),
    ]
    + plants_urls
    + political_culture_urls
    + cfflch_urls
)
