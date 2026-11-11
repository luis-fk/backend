from typing import Any

import pytest
from django.conf import settings
from django.core.management.base import CommandError

from backend.local_databases import remote_databases, require_local_databases
from tests import conftest

POSTGRES = "django.db.backends.postgresql"


def postgres(host: str) -> dict[str, Any]:
    return {"ENGINE": POSTGRES, "HOST": host, "PASSWORD": "secret-password"}


def test_this_machine_and_sqlite_are_local() -> None:
    databases = {
        "default": postgres("localhost"),
        "plants_db": postgres("127.0.0.1"),
        "political_culture_db": postgres("::1"),
        "cfflch_db": postgres(""),
        "news_podcast_db": postgres("/var/run/postgresql"),
        "ci": {"ENGINE": "django.db.backends.sqlite3", "NAME": "dummy.db", "HOST": ""},
    }

    assert remote_databases(databases) == []


def test_a_database_on_another_machine_is_remote() -> None:
    databases = {
        "default": postgres("localhost"),
        "plants_db": postgres("x.proxy.rlwy.net"),
    }

    assert remote_databases(databases) == ["plants_db (x.proxy.rlwy.net)"]


def test_the_commands_stop_on_a_remote_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "DATABASES", {"default": postgres("x.proxy.rlwy.net")}
    )

    with pytest.raises(CommandError) as error:
        require_local_databases()

    assert "default (x.proxy.rlwy.net)" in str(error.value)
    assert "secret-password" not in str(error.value)


def test_the_commands_go_on_with_local_databases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": postgres("localhost")})

    require_local_databases()


def test_the_tests_stop_on_a_remote_database(
    monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> None:
    monkeypatch.setattr(
        settings, "DATABASES", {"default": postgres("x.proxy.rlwy.net")}
    )

    with pytest.raises(pytest.UsageError, match=r"default \(x\.proxy\.rlwy\.net\)"):
        conftest.pytest_configure(pytestconfig)
