import asyncio
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.test import Client

from cfflch.api.admission_status import routes
from cfflch.api.admission_status.routes import AdmissionStatusApi
from cfflch.api.admission_status.schemas import (
    StudentFoundResult,
    StudentNotFoundResult,
    StudentResult,
)
from cfflch.api.admission_status.service import OnStudentDone
from tests.api_tokens import bearer, user_token

FULANO = StudentFoundResult(
    student_name="Fulano de Tal",
    normalized_name="fulano de tal",
    year_found=2025,
    search_query="",
    pdf_url="https://vestibular.exemplo.br/aprovados.pdf",
    search_title="Aprovados 2025",
)
BELTRANA = StudentNotFoundResult(student_name="Beltrana Conceição")
DONE = ("admission_status_abc", {"type": "admission_status.done"})


@pytest.fixture
def task() -> Iterator[AsyncMock]:
    """The background search, which the route only has to start."""
    background = AsyncMock()
    with patch.object(AdmissionStatusApi, "_process_admission_task", background):
        yield background


def start_search(client: Client, body: str) -> tuple[int, Any]:
    response = client.post(
        "/api/cfflch/admission-status/",
        body,
        content_type="application/json",
        headers=bearer(user_token("cfflch")),
    )
    return response.status_code, response.json()


def test_a_search_starts_in_the_background_and_answers_at_once(
    client: Client, task: AsyncMock
) -> None:
    answer = start_search(
        client, '{"names": ["Fulano de Tal"], "year": 2025, "request_id": "abc"}'
    )

    assert answer == (202, {"message": "Processing started", "request_id": "abc"})
    task.assert_called_once_with(["Fulano de Tal"], 2025, "abc", None)


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("names=Fulano", "Invalid JSON"),
        ('{"year": 2025, "request_id": "abc"}', "Invalid request data"),
        (
            '{"names": ["Fulano"], "year": "este", "request_id": "abc"}',
            "Invalid request data",
        ),
    ],
    ids=["not json", "no names", "year not a number"],
)
def test_an_invalid_search_gets_400(
    client: Client, task: AsyncMock, body: str, error: str
) -> None:
    assert start_search(client, body) == (400, {"error": error})
    task.assert_not_called()


class FakeService:
    """Reports each student's results like the real service, then fails if told to."""

    def __init__(
        self, batches: list[list[StudentResult]], error: Exception | None = None
    ) -> None:
        self.batches = batches
        self.error = error

    async def check_admission_status(
        self,
        students_names: list[str],
        year: int,
        class_name: str | None = None,
        on_student_done: OnStudentDone | None = None,
    ) -> None:
        assert on_student_done is not None
        for entries in self.batches:
            await on_student_done(entries)
        if self.error:
            raise self.error


@pytest.fixture
def channel_layer() -> Iterator[MagicMock]:
    """A channel layer that records what the search sends."""
    with patch.object(routes, "get_channel_layer") as get_channel_layer:
        get_channel_layer.return_value.group_send = AsyncMock()
        yield get_channel_layer.return_value


def process(service: FakeService) -> None:
    """Runs the background part of search "abc" with service doing the search."""
    with patch.object(routes, "AdmissionStatusService", return_value=service):
        asyncio.run(
            AdmissionStatusApi()._process_admission_task(
                ["Fulano de Tal", "Beltrana Conceição"], 2025, "abc", None
            )
        )


def sent(channel_layer: MagicMock) -> list[tuple[Any, ...]]:
    return [awaited.args for awaited in channel_layer.group_send.await_args_list]


def results(entries: list[StudentResult]) -> tuple[str, dict[str, Any]]:
    return (
        "admission_status_abc",
        {
            "type": "admission_status.message",
            "message": [entry.model_dump() for entry in entries],
        },
    )


def test_each_students_results_go_to_the_request_socket_then_done(
    channel_layer: MagicMock,
) -> None:
    process(FakeService([[FULANO], [BELTRANA]]))

    assert sent(channel_layer) == [results([FULANO]), results([BELTRANA]), DONE]


def test_a_failed_search_still_tells_the_socket_it_is_done(
    channel_layer: MagicMock,
) -> None:
    process(FakeService([[FULANO]], error=RuntimeError("Tavily is down")))

    assert sent(channel_layer) == [results([FULANO]), DONE]


def test_a_message_that_fails_to_send_does_not_stop_the_others(
    channel_layer: MagicMock,
) -> None:
    channel_layer.group_send.side_effect = [
        ConnectionError("Redis is down"),
        None,
        None,
    ]

    process(FakeService([[FULANO], [BELTRANA]]))

    assert sent(channel_layer) == [results([FULANO]), results([BELTRANA]), DONE]
