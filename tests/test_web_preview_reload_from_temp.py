from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import chessdna.app as appmod
from chessdna.app import app


SAMPLE_PGN = """[Event \"Test\"]
[Site \"https://example.com\"]
[Date \"2026.02.12\"]
[Round \"-\"]
[White \"A\"]
[Black \"B\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


@pytest.fixture(autouse=True)
def _clear_fetch_store():
    appmod.FETCH_STORE.clear()
    yield
    appmod.FETCH_STORE.clear()


def test_analyze_can_reload_preview_token_from_temp(tmp_path, monkeypatch):
    """If FETCH_STORE is empty (e.g., server restart), preview_token can reload from temp."""

    # Redirect temp dir to a test-local folder.
    monkeypatch.setattr(appmod, "FETCH_TMP_DIR", tmp_path)

    token = "tok_reload"
    (tmp_path / f"{token}.pgn").write_text(SAMPLE_PGN, encoding="utf-8")
    (tmp_path / f"{token}.json").write_text(
        json.dumps({"platform": "lichess", "created_at": 0, "fetch_max": 1}, ensure_ascii=False),
        encoding="utf-8",
    )

    c = TestClient(app)
    r = c.post(
        "/analyze",
        data={
            "preview_token": token,
            "game_idx": "0",  # select the first game
            "fetch_max": "1",
            "engine_path": "__missing_stockfish__",
            "time_per_move": "0.01",
            "max_plies": "10",
        },
    )

    assert r.status_code == 200
    assert "Download JSON" in r.text
    assert "/download/" in r.text
