from django.contrib import admin
from django.urls import path
from .views import MessageView

urlpatterns = [
    path("admin/", admin.site.urls),
    path('message/', MessageView.as_view(), name='message'),
]
