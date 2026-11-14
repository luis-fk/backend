import importlib
from pathlib import Path

import pytest
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import CreateModel
from django.db.migrations.recorder import MigrationRecorder
from django.db.models.fields import NOT_PROVIDED

APP = "news_podcast"
SQUASHED = (APP, "0001_squashed_0007_no_code_defaults")
DEFAULTS = (APP, "0007_no_code_defaults")
# Production before the release: every migration up to the feeds.
PRODUCTION = [
    (APP, name)
    for name in (
        "0001_initial",
        "0002_prompt_defaults",
        "0003_episode_script_words",
        "0004_selection_prompt_coverage",
        "0005_starting_values_from_code",
        "0006_feed",
    )
]
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / APP / "migrations"


def plan(
    monkeypatch: pytest.MonkeyPatch,
    applied: list[tuple[str, str]],
    target: tuple[str, str],
) -> list[tuple[str, str]]:
    """The migrations migrate would run to reach target, with the recorder faked, so
    no database is read."""
    # A new dict on each call: the loader adds or removes the squash's key.
    monkeypatch.setattr(
        MigrationRecorder, "applied_migrations", lambda self: dict.fromkeys(applied)
    )
    executor = MigrationExecutor(connections["news_podcast_db"])
    return [
        (migration.app_label, migration.name)
        for migration, _ in executor.migration_plan([target])
    ]


def test_an_empty_database_runs_only_the_squashed_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert plan(monkeypatch, [], SQUASHED) == [SQUASHED]


def test_production_runs_only_the_defaults_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert plan(monkeypatch, PRODUCTION, DEFAULTS) == [DEFAULTS]


def test_the_squashed_migration_holds_no_starting_value() -> None:
    module = importlib.import_module(f"{APP}.migrations.{SQUASHED[1]}")
    defaults = {
        (operation.name.lower(), name)
        for operation in module.Migration.operations
        if isinstance(operation, CreateModel)
        for name, field in operation.fields
        if field.default is not NOT_PROVIDED
    }
    source = (MIGRATIONS_DIR / f"{SQUASHED[1]}.py").read_text(encoding="utf-8")

    assert defaults == {
        ("episode", "usage"),
        ("feed", "active"),
        ("podcastsettings", "paused"),
    }
    assert "import news_podcast" not in source
    assert "functools" not in source
