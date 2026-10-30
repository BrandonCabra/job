import random
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def get_with_backoff(
    url: str,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> requests.Response:
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, **kwargs)
        except requests.RequestException:
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt) + random.uniform(0, 0.25))
            continue
        if response.status_code not in RETRYABLE_STATUS_CODES or attempt == max_attempts - 1:
            return response
        delay = _retry_after(response.headers.get("Retry-After"))
        time.sleep(delay if delay is not None else base_delay * (2**attempt) + random.uniform(0, 0.25))
    raise RuntimeError("No se pudo completar la solicitud HTTP")
