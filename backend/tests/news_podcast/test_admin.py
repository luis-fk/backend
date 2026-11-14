from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import models
from django.forms.models import model_to_dict
from django.test import Client, RequestFactory
from pytest_django import DjangoAssertNumQueries

from news_podcast.models import (
    LESSON_PROMPT_FIELDS,
    Area,
    Episode,
    Feed,
    LessonSettings,
    PodcastSettings,
    Topic,
    placeholder_error,
)
from tests.news_podcast.factories import (
    create_area,
    create_lesson_row,
    create_lesson_settings,
    create_settings,
    create_topic,
)

SETTINGS_URL = "/admin/news_podcast/podcastsettings/"
EPISODES_URL = "/admin/news_podcast/episode/"
FEEDS_URL = "/admin/news_podcast/feed/"
AREAS_URL = "/admin/news_podcast/area/"
TOPICS_URL = "/admin/news_podcast/topic/"
LESSON_URL = "/admin/news_podcast/lessonsettings/"
DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])


def form_data(row: models.Model, **changes: Any) -> dict[str, Any]:
    data = {**model_to_dict(row), **changes}
    del data["id"]
    return data


@DATABASES
def test_without_the_row_the_settings_page_says_to_run_the_seed(
    admin_client: Client,
) -> None:
    response = admin_client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert "seed_news_podcast" in response.content.decode()
    assert not PodcastSettings.objects.exists()


@DATABASES
def test_the_settings_page_opens_the_row(admin_client: Client) -> None:
    row = create_settings()

    response = admin_client.get(SETTINGS_URL)

    assert response.status_code == 302
    assert response["Location"] == f"{SETTINGS_URL}{row.pk}/change/"


@DATABASES
def test_the_admin_index_never_queries_the_podcast_database(
    admin_client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(0, using="news_podcast_db"):
        response = admin_client.get("/admin/")

    assert response.status_code == 200
    page = response.content.decode()
    assert f'href="{AREAS_URL}"' in page
    assert f'href="{TOPICS_URL}"' in page


@DATABASES
@pytest.mark.parametrize("with_row", [True, False])
def test_the_settings_page_needs_the_permission_before_anything_else(
    client: Client, with_row: bool
) -> None:
    if with_row:
        create_settings()
    staff = get_user_model().objects.create_user(
        username="ana", password="senha", is_staff=True
    )
    client.force_login(staff)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 403
    assert list(get_messages(response.wsgi_request)) == []


@DATABASES
def test_the_settings_row_can_be_neither_added_nor_deleted(
    admin_client: Client,
) -> None:
    row = create_settings()

    assert admin_client.get(f"{SETTINGS_URL}add/").status_code == 403
    assert admin_client.get(f"{SETTINGS_URL}{row.pk}/delete/").status_code == 403


@DATABASES
def test_the_admin_saves_a_change(admin_client: Client) -> None:
    row = create_settings()

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
    row = create_settings()
    before = row.script_prompt

    response = admin_client.post(
        f"{SETTINGS_URL}{row.pk}/change/",
        form_data(row, script_prompt="Oi, {ouvinte}!"),
    )

    errors = response.context["adminform"].form.errors
    assert "{ouvinte}" in errors["script_prompt"][0]
    row.refresh_from_db()
    assert row.script_prompt == before


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


@DATABASES
def test_an_empty_feed_list_opens_empty(admin_client: Client) -> None:
    response = admin_client.get(FEEDS_URL)

    assert response.status_code == 200
    assert not Feed.objects.exists()


@DATABASES
def test_the_topics_list_shows_when_a_sent_lesson_taught_each_topic(
    admin_client: Client,
) -> None:
    area = create_area(name="O Congresso e as leis")
    taught = create_topic(area, title="Como o Congresso derruba um veto", position=11)
    tried = create_topic(area, title="Sanção e veto", position=10)
    create_topic(area, title="Impeachment", position=22)
    create_lesson_row(taught, started_at=datetime(2026, 11, 13, 1, 30, tzinfo=UTC))
    create_lesson_row(tried, status=Episode.Status.FAILED)
    create_lesson_row(tried, status=Episode.Status.NOT_SENT)
    create_lesson_row(tried, kind=Episode.Kind.NEWS)

    page = admin_client.get(TOPICS_URL).content.decode()

    # 01:30 UTC on the 13th is still the 12th in São Paulo.
    assert page.count('<td class="field-taught">12/11/2026</td>') == 1
    assert page.count('<td class="field-taught">-</td>') == 2
    for column in ["title", "area", "position", "active", "taught"]:
        assert f"column-{column}" in page
    assert "Taught on (Brasília)" in page


@DATABASES
def test_the_topics_list_filters_by_area_and_by_active(admin_client: Client) -> None:
    congress = create_area(name="O Congresso e as leis", position=3)
    justice = create_area(name="Justiça", position=2)
    create_topic(congress, title="Como o Congresso derruba um veto")
    create_topic(justice, title="O STF: o que julga")
    create_topic(justice, title="O CNJ: quem fiscaliza os juízes", active=False)

    by_area = admin_client.get(TOPICS_URL, {"area__id__exact": justice.pk})
    inactive = admin_client.get(TOPICS_URL, {"active__exact": "0"})

    # The changelist would apply a lookup from the URL even without the sidebar.
    filters = [spec.title for spec in by_area.context["cl"].filter_specs]
    assert filters == ["area", "active"]
    listed = [str(topic) for topic in by_area.context["cl"].result_list]
    assert listed == ["O STF: o que julga", "O CNJ: quem fiscaliza os juízes"]
    assert [str(topic) for topic in inactive.context["cl"].result_list] == [
        "O CNJ: quem fiscaliza os juízes"
    ]


@DATABASES
def test_the_catalog_lists_keep_one_order_through_ties(admin_client: Client) -> None:
    first = create_area(name="Primeira", position=1)
    tied = create_area(name="Segunda", position=1)
    create_topic(first, title="Tópico B", position=1)
    create_topic(first, title="Tópico A", position=1)
    create_topic(tied, title="Tópico C", position=0)
    # An update moves a row to the end of its table on PostgreSQL, so the tied rows
    # created first no longer come back first on their own: only the pk orders them.
    Area.objects.filter(pk=first.pk).update(position=1)
    Topic.objects.filter(title="Tópico B").update(position=1)

    areas = admin_client.get(AREAS_URL).context["cl"].result_list
    topics = admin_client.get(TOPICS_URL).context["cl"].result_list

    assert [str(area) for area in areas] == ["Primeira", "Segunda"]
    assert [str(topic) for topic in topics] == ["Tópico B", "Tópico A", "Tópico C"]


@DATABASES
def test_a_taught_topic_and_its_area_stay_when_the_admin_deletes_them(
    admin_client: Client,
) -> None:
    area = create_area()
    topic = create_topic(area)
    create_lesson_row(topic)

    for url in [f"{TOPICS_URL}{topic.pk}/delete/", f"{AREAS_URL}{area.pk}/delete/"]:
        assert "Cannot delete" in admin_client.get(url).content.decode()
        admin_client.post(url, {"post": "yes"})
    admin_client.post(
        TOPICS_URL,
        {"action": "delete_selected", "_selected_action": [topic.pk], "post": "yes"},
    )

    assert Topic.objects.filter(pk=topic.pk).exists()
    assert Area.objects.filter(pk=area.pk).exists()


@DATABASES
def test_the_kind_filter_lists_the_lessons_and_adds_up_their_cost(
    admin_client: Client,
) -> None:
    Episode.objects.create(
        started_at=datetime(2026, 11, 13, 9, 40, tzinfo=UTC),
        status=Episode.Status.SENT,
        cost_usd=0.10,
    )
    create_lesson_row(
        started_at=datetime(2026, 11, 13, 10, 0, tzinfo=UTC), cost_usd=0.20
    )
    create_lesson_row(
        started_at=datetime(2026, 11, 15, 10, 0, tzinfo=UTC), cost_usd=0.30
    )

    response = admin_client.get(EPISODES_URL, {"kind__exact": "lesson"})
    page = response.content.decode()

    filters = [spec.title for spec in response.context["cl"].filter_specs]
    assert filters == ["kind", "status"]
    assert page.count('<td class="field-kind">Lesson</td>') == 2
    assert '<td class="field-kind">News</td>' not in page
    assert "<strong>R$ 2,75</strong>" in page


@DATABASES
def test_a_lesson_row_shows_its_topic_story_and_pages(admin_client: Client) -> None:
    topic = create_topic(create_area(), title="Como o Congresso derruba um veto")
    lesson = create_lesson_row(
        topic,
        story_title="Congresso derruba veto ao <marco> & cia",
        pages=[
            {
                "title": "Entenda o veto & a sessão",
                "url": "https://www12.senado.leg.br/veto?a=1&b=2",
            },
            {"title": "Vetos", "url": "https://www.camara.leg.br/vetos"},
        ],
    )

    page = admin_client.get(f"{EPISODES_URL}{lesson.pk}/change/").content.decode()

    assert '<div class="readonly">Lesson</div>' in page
    assert "Como o Congresso derruba um veto" in page
    assert "Congresso derruba veto ao &lt;marco&gt; &amp; cia" in page
    assert (
        "Entenda o veto &amp; a sessão: https://www12.senado.leg.br/veto?a=1&amp;b=2"
    ) in page
    assert "Vetos: https://www.camara.leg.br/vetos" in page


@DATABASES
def test_a_lesson_row_with_odd_pages_still_opens_and_links_nothing(
    admin_client: Client,
) -> None:
    lesson = create_lesson_row(
        pages=[{"url": "javascript:alert(1)"}, {"title": "Sem endereço"}]
    )

    response = admin_client.get(f"{EPISODES_URL}{lesson.pk}/change/")

    page = response.content.decode()
    assert response.status_code == 200
    assert ": javascript:alert(1)" in page
    assert "Sem endereço: " in page
    assert 'href="javascript:' not in page


@DATABASES
def test_without_the_lesson_row_the_page_says_to_run_the_seed(
    admin_client: Client,
) -> None:
    response = admin_client.get(LESSON_URL)

    assert response.status_code == 200
    assert "configurações da aula" in response.content.decode()
    assert "seed_news_podcast" in response.content.decode()
    assert not LessonSettings.objects.exists()


@DATABASES
def test_the_lesson_settings_page_opens_the_row(admin_client: Client) -> None:
    row = create_lesson_settings()

    response = admin_client.get(LESSON_URL)

    assert response.status_code == 302
    assert response["Location"] == f"{LESSON_URL}{row.pk}/change/"


@DATABASES
def test_the_lesson_row_can_be_neither_added_nor_deleted_and_asks_no_query(
    admin_client: Client, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    row = create_lesson_settings()
    model_admin = admin.site.get_model_admin(LessonSettings)
    request = RequestFactory().get(LESSON_URL)

    with django_assert_num_queries(0, using="news_podcast_db"):
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_delete_permission(request, row)
    assert admin_client.get(f"{LESSON_URL}add/").status_code == 403
    assert admin_client.get(f"{LESSON_URL}{row.pk}/delete/").status_code == 403


@DATABASES
@pytest.mark.parametrize("with_row", [True, False])
def test_the_lesson_page_needs_the_permission_before_anything_else(
    client: Client, with_row: bool
) -> None:
    if with_row:
        create_lesson_settings()
    staff = get_user_model().objects.create_user(
        username="ana", password="senha", is_staff=True
    )
    client.force_login(staff)

    response = client.get(LESSON_URL)

    assert response.status_code == 403
    assert list(get_messages(response.wsgi_request)) == []


@DATABASES
@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"min_minutes": 0}, "min_minutes"),
        ({"max_minutes": 10}, "max_minutes"),
        ({"min_minutes": 9, "max_minutes": 8}, "max_minutes"),
        ({"review_prompt": "Revise {topico}."}, "review_prompt"),
        ({"voice_model": "openai:gpt-4o-mini-tts"}, "voice_model"),
    ],
)
def test_the_lesson_form_refuses_a_bad_value_and_keeps_the_row(
    admin_client: Client, changes: dict[str, Any], field: str
) -> None:
    row = create_lesson_settings()
    before = model_to_dict(row)

    response = admin_client.post(
        f"{LESSON_URL}{row.pk}/change/", form_data(row, **changes)
    )

    assert field in response.context["adminform"].form.errors
    row.refresh_from_db()
    assert model_to_dict(row) == before


@DATABASES
def test_the_lesson_form_saves_a_lesson_of_1_to_9_minutes(admin_client: Client) -> None:
    row = create_lesson_settings()

    response = admin_client.post(
        f"{LESSON_URL}{row.pk}/change/", form_data(row, min_minutes=1, max_minutes=9)
    )

    assert response.status_code == 302
    row.refresh_from_db()
    assert (row.min_minutes, row.max_minutes) == (1, 9)


@DATABASES
@pytest.mark.parametrize(("field", "fields"), list(LESSON_PROMPT_FIELDS.items()))
def test_the_lesson_form_shows_the_placeholder_message_and_saves_a_full_prompt(
    admin_client: Client, field: str, fields: tuple[str, ...]
) -> None:
    row = create_lesson_settings()
    url = f"{LESSON_URL}{row.pk}/change/"
    full = " ".join(f"{{{name}}}" for name in fields) + " {{literal}}"

    refused = admin_client.post(url, form_data(row, **{field: "Oi, {ouvinte}!"}))
    saved = admin_client.post(url, form_data(row, **{field: full}))

    errors = refused.context["adminform"].form.errors[field]
    assert errors == [placeholder_error("Oi, {ouvinte}!", fields)]
    assert saved.status_code == 302
    row.refresh_from_db()
    assert getattr(row, field) == full


@DATABASES
@pytest.mark.parametrize(
    "name", ["gemini-3.8-flash-tts", "google_genai:gemini-3.8-flash-tts"]
)
def test_the_lesson_form_saves_a_gemini_voice(admin_client: Client, name: str) -> None:
    row = create_lesson_settings()

    response = admin_client.post(
        f"{LESSON_URL}{row.pk}/change/", form_data(row, voice_model=name)
    )

    assert response.status_code == 302
    row.refresh_from_db()
    assert row.voice_model == name
