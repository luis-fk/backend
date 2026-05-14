from django.urls import path

from plants.api.users.routes import UserApi

users_urls = [
    path("api/plants/users/<str:name>/", UserApi.as_view(), name="plants_user"),
]
