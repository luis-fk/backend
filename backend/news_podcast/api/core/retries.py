import re
from typing import Any

MAX_ATTEMPTS = 3
MAX_RETRY_DELAY_SECONDS = 90.0
RATE_LIMIT_WAIT_SECONDS = 30.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
SECONDS_PATTERN = re.compile(r"([\d.]+)s")


def backoff_seconds(attempt: int) -> float:
    return float(min(5 * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS))


# Gemini's error body reaches both the voice (the Interactions API's answer) and the
# text models (google-genai's error), so it is read here, for the two of them.
def error_details(error: dict[str, Any]) -> list[dict[str, Any]]:
    details = (error.get("error") or {}).get("details") or []
    return [detail for detail in details if isinstance(detail, dict)]


def is_daily_quota(error: dict[str, Any]) -> bool:
    for detail in error_details(error):
        for violation in detail.get("violations") or []:
            quota_id = str(violation.get("quotaId", ""))
            metric = str(violation.get("quotaMetric", ""))
            if "PerDay" in quota_id or "per_day" in metric:
                return True
    return False


def retry_delay(error: dict[str, Any]) -> float | None:
    for detail in error_details(error):
        match = SECONDS_PATTERN.fullmatch(str(detail.get("retryDelay", "")))
        if match:
            return min(float(match.group(1)) + 1, MAX_RETRY_DELAY_SECONDS)
    return None
