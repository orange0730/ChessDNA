from __future__ import annotations

from fastapi.testclient import TestClient

from chessdna.app import app


SAMPLE_PGN = """
[Event \"Casual Game\"]
[Site \"https://lichess.org/\"]
[Date \"2024.01.01\"]
[Round \"-\"]
[White \"Alice\"]
[Black \"Bob\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 1-0
"""


def test_web_analyze_accepts_pgn_text_even_without_engine():
    """Smoke test the /analyze route (pgn_text path).

    Even if Stockfish is missing, the app should still return an HTML report page.
    """

    c = TestClient(app)
    r = c.post(
        "/analyze",
        data={
            "pgn_text": SAMPLE_PGN,
            "engine_path": "__missing_stockfish__",
            "time_per_move": "0.01",
            "max_plies": "30",
        },
    )

    assert r.status_code == 200
    # report.html should include download links (report_id is embedded in the URL).
    assert "Download JSON" in r.text
    assert "/download/" in r.text
