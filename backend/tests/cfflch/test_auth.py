from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponseBase
from django.test import Client

from cfflch.api.admission_status.routes import AdmissionStatusApi
from cfflch.models import AdmissionResult, ClassRoom
from tests.api_tokens import (
    api_key,
    bearer,
    login_token,
    make_token,
    saved_person,
    unknown_api_key,
    user_token,
)

Send = Callable[[Client, dict[str, str]], HttpResponseBase]


def list_class_rooms(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.get("/api/cfflch/class-rooms/", headers=headers)


def list_results(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.get("/api/cfflch/admission-results/", {"year": 2025}, headers=headers)


def update_result(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.patch(
        "/api/cfflch/admission-results/1/",
        {"approved": True},
        content_type="application/json",
        headers=headers,
    )


def delete_result(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.delete("/api/cfflch/admission-results/1/", headers=headers)


def start_search(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.post(
        "/api/cfflch/admission-status/",
        {"names": ["Ana Souza"], "year": 2025, "request_id": "abc"},
        content_type="application/json",
        headers=headers,
    )


def find_user(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.get("/api/cfflch/users/ana", headers=headers)


REQUESTS = [list_class_rooms, list_results, update_result, delete_result, start_search]
# What each request answers a cfflch user, with the empty_database fixture.
STATUSES = [
    (list_class_rooms, 200),
    (list_results, 200),
    (update_result, 404),
    (delete_result, 404),
    (start_search, 202),
]


@pytest.fixture
def empty_database() -> Iterator[None]:
    """No class rooms or results, and searches that end right away."""
    with (
        patch.object(ClassRoom.objects, "all", return_value=[]),
        patch.object(AdmissionResult.objects, "filter"),
        patch.object(AdmissionResult.objects, "prefetch_related") as result,
        patch.object(AdmissionStatusApi, "_process_admission_task", AsyncMock()),
    ):
        result.return_value.get.side_effect = AdmissionResult.DoesNotExist
        yield


@pytest.mark.parametrize("send", REQUESTS)
def test_requests_without_a_token_get_401(client: Client, send: Send) -> None:
    assert send(client, {}).status_code == 401


@pytest.mark.parametrize("send", REQUESTS)
def test_tokens_for_another_app_get_401(client: Client, send: Send) -> None:
    assert send(client, bearer(user_token("plants"))).status_code == 401


@pytest.mark.usefixtures("empty_database")
@pytest.mark.parametrize(("send", "status"), STATUSES)
def test_any_cfflch_user_gets_in(client: Client, send: Send, status: int) -> None:
    """The results have no owner: every cfflch user shares them."""
    assert send(client, bearer(user_token("cfflch", "8"))).status_code == status


@pytest.mark.django_db
@pytest.mark.usefixtures("empty_database")
@pytest.mark.parametrize(("send", "status"), STATUSES)
def test_any_cfflch_api_key_gets_in(client: Client, send: Send, status: int) -> None:
    """start_search is an async view: it looks the key up through sync_to_async."""
    assert send(client, bearer(api_key("cfflch", 8))).status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("send", REQUESTS)
def test_api_keys_for_another_app_get_401(client: Client, send: Send) -> None:
    assert send(client, bearer(api_key("plants"))).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("send", REQUESTS)
def test_inactive_api_keys_get_401(client: Client, send: Send) -> None:
    headers = bearer(api_key("cfflch", active=False))

    assert send(client, headers).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("send", REQUESTS)
def test_unknown_api_keys_get_401(client: Client, send: Send) -> None:
    assert send(client, bearer(unknown_api_key())).status_code == 401


def test_the_login_lookup_without_a_token_gets_401(client: Client) -> None:
    assert find_user(client, {}).status_code == 401


@pytest.mark.parametrize(
    ("app", "purpose"),
    [("cfflch", "user"), ("plants", "login")],
    ids=["user token", "another app's login token"],
)
def test_the_login_lookup_with_another_token_gets_401(
    client: Client, app: str, purpose: str
) -> None:
    headers = bearer(make_token(sub="7", app=app, purpose=purpose))

    assert find_user(client, headers).status_code == 401


def test_the_login_lookup_runs_with_a_login_token(client: Client) -> None:
    AuthUser = get_user_model()
    with patch.object(AuthUser.objects, "using") as using:
        using.return_value.get.side_effect = AuthUser.DoesNotExist
        response = find_user(client, bearer(login_token("cfflch")))

    assert response.status_code == 404
    using.return_value.get.assert_called_once_with(username="ana", is_active=True)


@pytest.mark.access_check
@pytest.mark.django_db(databases=["default", "cfflch_db"])
@pytest.mark.usefixtures("empty_database")
@pytest.mark.parametrize(
    ("send", "status"), [(list_class_rooms, 200), (start_search, 202)]
)
@pytest.mark.parametrize(
    ("is_active", "active"),
    [(True, True), (False, True), (True, False)],
    ids=["can use cfflch", "Active unticked", "cfflch unticked"],
)
def test_only_people_who_can_use_cfflch_get_in(
    client: Client, send: Send, status: int, is_active: bool, active: bool
) -> None:
    """start_search is an async view: the check runs through sync_to_async."""
    user_id = saved_person("cfflch", is_active=is_active, active=active)
    expected = status if is_active and active else 401

    assert send(client, bearer(user_token("cfflch", user_id))).status_code == expected
