from api_keys.models import ApiKey
from backend.apps_routers import AppsRouter


def test_api_keys_live_only_in_the_default_database() -> None:
    router = AppsRouter()

    assert router.db_for_read(ApiKey) == "default"
    assert router.allow_migrate("default", "api_keys") is True
    assert router.allow_migrate("plants_db", "api_keys") is False
