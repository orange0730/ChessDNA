from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from chessdna.app import FETCH_STORE, app
from chessdna.core.pgn_utils import preview_games


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


def test_analyze_selection_error_keeps_user_settings_in_form():
    previews, raw_games = preview_games(SAMPLE_PGN, max_games=2)
    token = "t123"
    FETCH_STORE[token] = {"platform": "lichess", "previews": previews, "games": raw_games}

    c = TestClient(app)
    r = c.post(
        "/analyze",
        data={
            "preview_token": token,
            # no game_idx => should trigger selection error
            "platform": "lichess",
            "lichess_user": "someone",
            "fetch_max": "2",
            "player_name": "orange",
            "engine_path": "C:/engine/stockfish.exe",
            "time_per_move": "0.12",
            "max_plies": "123",
        },
    )

    assert r.status_code == 400

    # Ensure the form keeps the user-entered values.
    assert 'name="player_name"' in r.text
    assert 'value="orange"' in r.text

    assert 'name="engine_path"' in r.text
    assert "C:/engine/stockfish.exe" in r.text

    m = re.search(r'name=\"time_per_move\"[^>]*value=\"([^\"]+)\"', r.text)
    assert m
    assert m.group(1).startswith("0.12")

    assert 'name="max_plies"' in r.text
    assert 'value="123"' in r.text
