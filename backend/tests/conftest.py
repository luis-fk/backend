import langsmith
import pytest
from django.conf import settings

from backend.local_databases import remote_databases


def pytest_configure(config: pytest.Config) -> None:
    """The tests stay on this machine, though backend/.env may hold the production
    URLs, where pytest-django would create its test_* databases, and may turn on
    LangSmith tracing, which would send the tests' LangChain calls over the network."""
    remote = remote_databases(settings.DATABASES)
    if remote:
        raise pytest.UsageError(
            f"The tests only run on local databases, and these are not: "
            f"{', '.join(remote)}. Check backend/.env."
        )
    langsmith.configure(enabled=False)


@pytest.fixture(autouse=True)
def skip_the_access_check(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every user token and API key also needs its person to still be able to use
    the app, which reads their row in the app's Users and their auth user
    (backend/api_auth.py). Most tests make up user ids, many without a database, so
    the check lets them in; the tests marked access_check run it."""
    if request.node.get_closest_marker("access_check") is None:
        monkeypatch.setattr("backend.api_auth.can_use", lambda app, user_id: True)
