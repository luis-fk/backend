from django.urls import path

from cfflch.api.admission_results.routes import (
    AdmissionResultDetailApi,
    AdmissionResultsListApi,
)
from cfflch.api.admission_status.routes import AdmissionStatusApi
from cfflch.api.class_rooms.routes import ClassRoomsListApi
from cfflch.api.users.routes import UserApi

admission_status_urls = [
    path(
        "api/cfflch/admission-status/",
        AdmissionStatusApi.as_view(),
        name="admission_status",
    ),
]

admission_results_urls = [
    path(
        "api/cfflch/admission-results/",
        AdmissionResultsListApi.as_view(),
        name="admission_results_list",
    ),
    path(
        "api/cfflch/admission-results/<int:pk>/",
        AdmissionResultDetailApi.as_view(),
        name="admission_results_detail",
    ),
]

class_rooms_urls = [
    path(
        "api/cfflch/class-rooms/",
        ClassRoomsListApi.as_view(),
        name="class_rooms_list",
    ),
]

users_urls = [
    path(
        "api/cfflch/users/<str:name>",
        UserApi.as_view(),
        name="cfflch_user",
    ),
]

cfflch_urls = (
    admission_status_urls + admission_results_urls + class_rooms_urls + users_urls
)
