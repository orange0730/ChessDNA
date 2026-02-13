from __future__ import annotations

import requests

from chessdna.core import http


class _Resp:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise requests.HTTPError(f"{self.status_code}")


def test_get_retries_on_429_then_succeeds(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(1)
        # 1st call: rate limited
        if len(calls) == 1:
            return _Resp(429, headers={"Retry-After": "0"})
        # 2nd call: ok
        return _Resp(200)

    def fake_sleep(s: float):
        sleeps.append(float(s))

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", fake_sleep)

    r = http.get("https://example.com", max_retries=3, backoff_seconds=0.5)
    assert r.status_code == 200
    assert len(calls) == 2
    # honored Retry-After=0 => sleep(0)
    assert sleeps == [0.0]


def test_get_raises_fetcherror_after_retries(monkeypatch):
    sleeps: list[float] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError("boom")

    def fake_sleep(s: float):
        sleeps.append(float(s))

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", fake_sleep)

    try:
        http.get("https://example.com", max_retries=2, backoff_seconds=0.5)
        assert False, "expected FetchError"
    except http.FetchError as e:
        msg = str(e)
        assert "example.com" in msg
        assert "boom" in msg

    # sleep called once per retry (not after final attempt)
    assert len(sleeps) == 2
