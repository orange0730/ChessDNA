from __future__ import annotations

from fastapi.testclient import TestClient

from chessdna.app import app, FETCH_STORE


def test_analyze_requires_selection_when_using_preview_token():
    """If user enters preview mode, they must explicitly select >=1 game.

    This prevents accidental analyze of all fetched games.
    """

    token = "tok_test"
    FETCH_STORE[token] = {
        "platform": "lichess",
        "previews": [
            {
                "idx": 0,
                "white": "A",
                "black": "B",
                "result": "1-0",
                "date": "2026.02.12",
                "event": "Test",
                "site": "https://example.com",
            }
        ],
        "games": [
            "[Event \"Test\"]\n[Site \"https://example.com\"]\n[Date \"2026.02.12\"]\n[Round \"-\"]\n[White \"A\"]\n[Black \"B\"]\n[Result \"1-0\"]\n\n1. e4 e5 2. Nf3 Nc6 1-0\n"
        ],
    }

    c = TestClient(app)
    r = c.post(
        "/analyze",
        data={
            "preview_token": token,
            "platform": "lichess",
            "lichess_user": "someone",
            "fetch_max": "1",
            "engine_path": "",
            "time_per_move": "0.01",
            "max_plies": "10",
        },
    )

    assert r.status_code == 400
    assert "Select at least 1 game" in r.text


def test_analyze_allows_pgn_text_even_if_preview_token_present():
    """If user has a preview_token but doesn't select games, allow fallback PGN input.

    This matches the client-side validation: pasting PGN text should still work.
    """

    token = "tok_test2"
    FETCH_STORE[token] = {
        "platform": "lichess",
        "previews": [],
        "games": [
            "[Event \"Test\"]\n\n1. e4 e5 1-0\n",
        ],
    }

    c = TestClient(app)
    r = c.post(
        "/analyze",
        data={
            "preview_token": token,
            "pgn_text": "[Event \"Fallback\"]\n\n1. d4 d5 1/2-1/2\n",
            "engine_path": "__missing_stockfish__",
            "time_per_move": "0.01",
            "max_plies": "10",
        },
    )

    assert r.status_code == 200
    assert "Download JSON" in r.text
    assert "/download/" in r.text
