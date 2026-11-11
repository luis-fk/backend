import pytest


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
