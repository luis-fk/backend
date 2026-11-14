import importlib

import pytest
from django.apps import apps
from django.db import connections
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import CreateModel
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.db.models.fields import NOT_PROVIDED

APP = "news_podcast"
SQUASHED = (APP, "0001_squashed_0007_no_code_defaults")


def plan(
    monkeypatch: pytest.MonkeyPatch,
    applied: list[tuple[str, str]],
    target: tuple[str, str],
) -> list[tuple[str, str]]:
    """The migrations migrate would run to reach target, with the recorder faked, so
    no database is read."""
    # A new dict on each call: the loader may add or remove keys.
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


def test_a_database_with_the_squash_recorded_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert plan(monkeypatch, [SQUASHED], SQUASHED) == []


def test_the_squashed_migration_is_the_app_s_first() -> None:
    # replace_migrations=False reads the files as they are, with no squash remapping.
    graph = MigrationLoader(None, replace_migrations=False).graph

    assert graph.root_nodes(APP) == [SQUASHED]


def test_the_models_need_no_new_migration() -> None:
    # makemigrations --check, without a database.
    loader = MigrationLoader(None, ignore_no_migrations=True)
    changes = MigrationAutodetector(
        loader.project_state(), ProjectState.from_apps(apps)
    ).changes(graph=loader.graph, trim_to_apps={APP}, convert_apps={APP})

    assert changes == {}


def test_the_squashed_migration_replaces_nothing_and_keeps_three_defaults() -> None:
    migration = importlib.import_module(f"{APP}.migrations.{SQUASHED[1]}").Migration
    defaults = {
        (operation.name.lower(), name)
        for operation in migration.operations
        if isinstance(operation, CreateModel)
        for name, field in operation.fields
        if field.default is not NOT_PROVIDED
    }

    assert migration.initial is True
    assert migration.dependencies == []
    assert migration.replaces == []
    assert defaults == {
        ("episode", "usage"),
        ("feed", "active"),
        ("podcastsettings", "paused"),
    }
