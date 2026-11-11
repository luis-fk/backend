from io import StringIO
from typing import Any

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

LOCAL = {"ENGINE": "django.db.backends.postgresql", "HOST": "localhost"}
REMOTE = {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "x.proxy.rlwy.net",
    "PASSWORD": "secret-password",
}


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The databases migrate ran on, in order; it doesn't really run."""
    databases: list[str] = []

    def migrate(name: str, **options: Any) -> None:
        assert name == "migrate"
        databases.append(options["database"])

    monkeypatch.setattr("backend.management.commands.migrate_all.call_command", migrate)
    return databases


def answer(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[str]:
    """Answers the confirmation with reply and returns the prompts shown."""
    prompts: list[str] = []

    def typed(prompt: str = "") -> str:
        prompts.append(prompt)
        return reply

    monkeypatch.setattr("builtins.input", typed)
    return prompts


def test_every_local_database_is_migrated_in_order(
    monkeypatch: pytest.MonkeyPatch, migrated: list[str]
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": LOCAL, "plants_db": LOCAL})

    call_command("migrate_all", stdout=StringIO())

    assert migrated == ["default", "plants_db"]


def test_nothing_is_migrated_when_a_database_is_remote(
    monkeypatch: pytest.MonkeyPatch, migrated: list[str]
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": LOCAL, "plants_db": REMOTE})
    prompts = answer(monkeypatch, "yes")

    with pytest.raises(CommandError, match="plants_db"):
        call_command("migrate_all", stdout=StringIO())

    assert migrated == []
    assert prompts == []


def test_production_shows_the_hosts_and_migrates_after_a_yes(
    monkeypatch: pytest.MonkeyPatch, migrated: list[str]
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": REMOTE, "plants_db": REMOTE})
    prompts = answer(monkeypatch, "yes")
    out = StringIO()

    call_command("migrate_all", production=True, stdout=out)

    assert len(prompts) == 1
    assert out.getvalue().count("x.proxy.rlwy.net") == 2
    assert "secret-password" not in out.getvalue() + prompts[0]
    assert migrated == ["default", "plants_db"]


def test_production_migrates_nothing_without_a_yes(
    monkeypatch: pytest.MonkeyPatch, migrated: list[str]
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": REMOTE})
    answer(monkeypatch, "y")

    with pytest.raises(CommandError):
        call_command("migrate_all", production=True, stdout=StringIO())

    assert migrated == []
