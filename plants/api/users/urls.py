from django.urls import path

from plants.api.users.routes import UserApi

users_urls = [
    path("api/user/<str:name>/", UserApi.as_view(), name="user"),
]
