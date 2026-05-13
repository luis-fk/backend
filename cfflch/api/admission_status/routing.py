from django.urls import path

from cfflch.api.admission_status import consumers

websocket_urlpatterns = [
    path(
        "ws/cfflch/admission_status/<str:requestId>",
        consumers.AdmissionStatusConsumer.as_asgi(),
    ),
]
