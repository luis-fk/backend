import pytest
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from api_keys.models import ApiKey
from plants.models import Users as PlantsUsers

OLD = [("api_keys", "0001_initial")]
NEW = [("api_keys", "0002_keys_for_several_apps")]


def migrate(target: list[tuple[str, str]]) -> MigrationExecutor:
    executor = MigrationExecutor(connections["default"])
    executor.migrate(target)
    return executor


# transaction=True: migrating runs schema changes, which a test wrapped in a
# transaction can't do on every database.
migrates = pytest.mark.django_db(
    databases=["default", "plants_db", "political_culture_db", "cfflch_db"],
    transaction=True,
)


@migrates
def test_the_migration_turns_each_old_key_into_a_key_for_its_app() -> None:
    maria = get_user_model().objects.create_user(username="maria")
    in_plants = PlantsUsers.objects.create(auth_user_id=maria.pk)
    try:
        executor = migrate(OLD)
        OldKey = executor.loader.project_state(OLD).apps.get_model("api_keys", "ApiKey")
        OldKey.objects.create(
            name="Bruno",
            app="plants",
            user_id=in_plants.pk,
            prefix="pk_a",
            key_hash="a",
        )
        OldKey.objects.create(
            name="Gone", app="cfflch", user_id=999, prefix="pk_b", key_hash="b"
        )
    finally:
        migrate(NEW)

    bruno = ApiKey.objects.get(name="Bruno")
    assert (bruno.auth_user_id, bruno.users) == (maria.pk, {"plants": in_plants.pk})
    # A key whose user is gone keeps acting as the same id, as before, with no person.
    gone = ApiKey.objects.get(name="Gone")
    assert (gone.auth_user_id, gone.users) == (None, {"cfflch": 999})


@migrates
def test_migrating_back_gives_each_key_the_first_of_its_apps() -> None:
    ApiKey.objects.create(name="One", users={"cfflch": 5}, prefix="pk_a", key_hash="a")
    ApiKey.objects.create(
        name="Two", users={"cfflch": 5, "plants": 3}, prefix="pk_b", key_hash="b"
    )
    try:
        executor = migrate(OLD)
        OldKey = executor.loader.project_state(OLD).apps.get_model("api_keys", "ApiKey")
        keys = {(key.name, key.app, key.user_id) for key in OldKey.objects.all()}
    finally:
        migrate(NEW)

    # The first in the apps' order: PostgreSQL's jsonb doesn't keep the keys' order.
    assert keys == {("One", "cfflch", 5), ("Two", "plants", 3)}
