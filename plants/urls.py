from django.contrib import admin
from django.urls import path
from views import HelloWorldView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("hello-world/", HelloWorldView.as_view(), name="hello-world"),
]
