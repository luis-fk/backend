from io import StringIO
from unittest.mock import patch

import jwt
import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import Client

from political_culture.models import ChatHistory


def api_token(*args: str) -> str:
    out = StringIO()
    call_command("api_token", *args, stdout=out)
    return out.getvalue().strip()


def test_the_api_accepts_the_printed_token(client: Client) -> None:
    token = api_token("7")

    with patch.object(ChatHistory.objects, "filter"):
        response = client.get(
            "/api/political-culture/chat-history/7",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


def test_the_token_lasts_the_given_days() -> None:
    claims = jwt.decode(
        api_token("7", "--days", "2"), settings.API_TOKEN_SECRET, algorithms=["HS256"]
    )

    assert claims["sub"] == "7"
    assert claims["app"] == "political-culture"
    assert claims["purpose"] == "user"
    assert claims["exp"] - claims["iat"] == 2 * 24 * 60 * 60


def test_the_token_lasts_at_least_a_day() -> None:
    with pytest.raises(CommandError):
        api_token("7", "--days", "0")
