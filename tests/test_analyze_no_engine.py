from chessdna.core.analyze import analyze_pgn_text


SAMPLE_PGN = """
[Event "Casual Game"]
[Site "https://lichess.org/"]
[Date "2024.01.01"]
[Round "-"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 1-0
"""


def test_analyze_degrades_gracefully_without_engine(tmp_path):
    # Use a definitely-missing engine path. The function should still return
    # a structurally valid report without raising.
    report = analyze_pgn_text(
        SAMPLE_PGN,
        engine_path=str(tmp_path / "__missing_stockfish__"),
        time_per_move=0.01,
        max_plies=60,
    )

    assert report.games
    g = report.games[0]
    assert g.plies
    # Without engine, CPL/accuracy should be None (not bogus zeros)
    assert g.plies[0].cpl is None
    assert g.avg_cpl_white is None
    assert g.accuracy_white is None


def test_analyze_clamps_inputs_like_web_settings(tmp_path):
    report = analyze_pgn_text(
        SAMPLE_PGN,
        engine_path=str(tmp_path / "__missing_stockfish__"),
        time_per_move=999,
        max_plies=999999,
    )

    assert report.time_per_move == 1.0
    assert report.max_plies == 800
