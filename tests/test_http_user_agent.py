from __future__ import annotations

import pytest

from chessdna.core import http


class _Resp:
    def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None


def test_http_sets_default_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _fake_get(url: str, params=None, headers=None, timeout=60):
        seen["url"] = url
        seen["headers"] = dict(headers or {})
        return _Resp(200)

    monkeypatch.setattr(http.requests, "get", _fake_get)

    http.get("https://example.com/api")
    assert "User-Agent" in seen["headers"]
    assert str(seen["headers"]["User-Agent"]).startswith("ChessDNA/")


def test_http_respects_custom_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _fake_get(url: str, params=None, headers=None, timeout=60):
        seen["headers"] = dict(headers or {})
        return _Resp(200)

    monkeypatch.setattr(http.requests, "get", _fake_get)

    http.get("https://example.com/api", headers={"User-Agent": "my-agent"})
    assert seen["headers"]["User-Agent"] == "my-agent"
