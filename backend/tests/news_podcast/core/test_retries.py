from typing import Any

from news_podcast.api.core.retries import is_daily_quota, retry_delay


def quota_error(quota_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": 429,
            "message": "Quota exceeded",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "7s",
                },
            ],
        }
    }


def test_daily_quota_is_told_apart_from_per_minute_limits() -> None:
    assert is_daily_quota(quota_error("GenerateRequestsPerDayPerProjectPerModel"))
    assert not is_daily_quota(quota_error("GenerateRequestsPerMinutePerProject"))
    assert retry_delay(quota_error("x")) == 8.0
