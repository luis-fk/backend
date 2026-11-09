from datetime import UTC, datetime
from typing import Any

import pytest
from django.forms.models import model_to_dict
from django.test import Client

from news_podcast.api.episode import config, prompts
from news_podcast.models import Episode, PodcastSettings

SETTINGS_URL = "/admin/news_podcast/podcastsettings/"
EPISODES_URL = "/admin/news_podcast/episode/"
DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])


def form_data(row: PodcastSettings, **changes: Any) -> dict[str, Any]:
    data = {**model_to_dict(row), **changes}
    del data["id"]
    return data


@DATABASES
def test_the_settings_open_with_the_values_in_the_code(admin_client: Client) -> None:
    response = admin_client.get(SETTINGS_URL, follow=True)

    form = response.context["adminform"].form
    assert form["text_model"].value() == config.TEXT_MODEL
    assert form["script_prompt"].value() == prompts.SCRIPT_PROMPT


@DATABASES
def test_there_is_a_single_settings_row(admin_client: Client) -> None:
    for _ in range(2):
        admin_client.get(SETTINGS_URL)
    row = PodcastSettings.objects.get()

    assert admin_client.get(f"{SETTINGS_URL}add/").status_code == 403
    assert admin_client.get(f"{SETTINGS_URL}{row.pk}/delete/").status_code == 403


@DATABASES
def test_the_admin_saves_a_change(admin_client: Client) -> None:
    row = PodcastSettings.objects.create()

    response = admin_client.post(
        f"{SETTINGS_URL}{row.pk}/change/", form_data(row, paused=True, max_minutes=15)
    )

    assert response.status_code == 302
    row.refresh_from_db()
    assert row.paused
    assert row.max_minutes == 15


@DATABASES
def test_the_admin_refuses_a_placeholder_the_service_does_not_fill(
    admin_client: Client,
) -> None:
    row = PodcastSettings.objects.create()

    response = admin_client.post(
        f"{SETTINGS_URL}{row.pk}/change/",
        form_data(row, script_prompt="Oi, {ouvinte}!"),
    )

    errors = response.context["adminform"].form.errors
    assert "{ouvinte}" in errors["script_prompt"][0]
    row.refresh_from_db()
    assert row.script_prompt == prompts.SCRIPT_PROMPT


@DATABASES
def test_the_history_shows_each_cost_and_the_total(admin_client: Client) -> None:
    for day, cost_usd in [(8, 0.10), (9, 0.08)]:
        Episode.objects.create(
            started_at=datetime(2026, 11, day, 9, 10, tzinfo=UTC),
            status=Episode.Status.SENT,
            duration_seconds=900.4,
            cost_usd=cost_usd,
        )

    page = admin_client.get(EPISODES_URL).content.decode()

    assert "09/11/2026 06:10" in page
    assert "15:00" in page
    # The cost column keeps "R$" with the number; the total uses a normal space.
    assert "R$\N{NO-BREAK SPACE}0,55" in page
    assert "R$\N{NO-BREAK SPACE}0,44" in page
    assert "<strong>R$ 0,99</strong>" in page
    assert admin_client.get(f"{EPISODES_URL}add/").status_code == 403


@DATABASES
def test_the_history_shows_the_voice_pace(admin_client: Client) -> None:
    Episode.objects.create(
        started_at=datetime(2026, 11, 9, 9, 40, tzinfo=UTC),
        status=Episode.Status.SENT,
        duration_seconds=900.0,
        script_words=2550,
        cost_usd=0.10,
    )
    Episode.objects.create(
        started_at=datetime(2026, 11, 8, 9, 10, tzinfo=UTC),
        status=Episode.Status.FAILED,
        cost_usd=0.02,
    )

    page = admin_client.get(EPISODES_URL).content.decode()

    assert '<td class="field-pace">170</td>' in page
    assert '<td class="field-pace">-</td>' in page
