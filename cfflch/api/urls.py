from django.urls import path

from cfflch.api.admission_status.routes import AdmissionStatusApi

admission_status_urls = [
    path(
        "api/cfflch/admission_status",
        AdmissionStatusApi.as_view(),
        name="admission_status",
    ),
]


cfflch_urls = admission_status_urls
