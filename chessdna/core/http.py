from __future__ import annotations

import time
from typing import Any, Callable

import requests


class FetchError(RuntimeError):
    pass


def get(
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    retry_statuses: set[int] | None = None,
) -> requests.Response:
    """HTTP GET with small retry/backoff for flaky public APIs.

    Retries on 429/5xx by default.
    """

    if retry_statuses is None:
        retry_statuses = {429, 500, 502, 503, 504}

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in retry_statuses and attempt < max_retries:
                # Honor Retry-After when provided.
                ra = r.headers.get("Retry-After")
                sleep_s = float(ra) if ra and ra.isdigit() else backoff_seconds * (2**attempt)
                time.sleep(min(sleep_s, 10.0))
                continue
            r.raise_for_status()
            return r
        except (requests.RequestException, ValueError) as e:
            last_exc = e
            if attempt >= max_retries:
                break
            time.sleep(min(backoff_seconds * (2**attempt), 10.0))

    raise FetchError(f"GET failed after {max_retries+1} tries: {url}\n{last_exc}")


def get_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    max_retries: int = 3,
) -> Any:
    r = get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
    )
    return r.json()
