from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from chessdna.app import app, FETCH_STORE


SAMPLE_PGN = """[Event \"Test1\"]
[Site \"https://example.com/1\"]
[Date \"2026.02.12\"]
[Round \"-\"]
[White \"A\"]
[Black \"B\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 1-0

[Event \"Test2\"]
[Site \"https://example.com/2\"]
[Date \"2026.02.11\"]
[Round \"-\"]
[White \"C\"]
[Black \"D\"]
[Result \"0-1\"]

1. d4 d5 2. c4 e6 0-1
"""


@pytest.fixture(autouse=True)
def _clear_fetch_store():
    FETCH_STORE.clear()
    yield
    FETCH_STORE.clear()


def test_preview_requires_username_when_platform_selected():
    c = TestClient(app)
    r = c.post("/preview", data={"platform": "lichess", "lichess_user": "", "fetch_max": "5"})
    assert r.status_code == 400


def test_preview_returns_token_and_game_list(monkeypatch):
    # Patch lichess fetch to avoid network.
    import chessdna.core.lichess as lichess

    def fake_fetch(user: str, max_games: int = 10) -> str:
        assert user == "someone"
        assert max_games == 2
        return SAMPLE_PGN

    monkeypatch.setattr(lichess, "fetch_user_games_pgn", fake_fetch)

    c = TestClient(app)
    r = c.post(
        "/preview",
        data={
            "platform": "lichess",
            "lichess_user": "someone",
            "fetch_max": "2",
        },
    )

    assert r.status_code == 200
    # Should include a preview_token hidden input.
    m = re.search(r"name=\"preview_token\" value=\"([a-f0-9]+)\"", r.text)
    assert m, "preview_token not found in HTML"
    token = m.group(1)
    assert token in FETCH_STORE

    store = FETCH_STORE[token]
    previews = list(store.get("previews") or [])
    games = list(store.get("games") or [])

    assert len(previews) == 2
    assert len(games) == 2
