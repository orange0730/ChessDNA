from __future__ import annotations

from pathlib import Path

from chessdna.core.pgn_utils import pgn_info, preview_games, split_pgn_games


def test_split_pgn_games_smoke():
    sample = Path(__file__).resolve().parents[1] / "_sample_orange_bot.pgn"
    txt = sample.read_text(encoding="utf-8")
    games = split_pgn_games(txt, max_games=50)
    assert len(games) >= 1
    assert all(g.strip().startswith("[") for g in games)


def test_preview_games_indices_and_fields():
    sample = Path(__file__).resolve().parents[1] / "_sample_orange_bot.pgn"
    txt = sample.read_text(encoding="utf-8")
    previews, raw = preview_games(txt, max_games=20)
    assert len(previews) == len(raw)
    assert [p.idx for p in previews] == list(range(len(previews)))
    # basic fields populated
    for p in previews:
        assert p.white
        assert p.black
        assert p.result
        assert p.date
        assert p.event
        assert p.site


def test_pgn_info_counts_games_and_plies():
    sample = Path(__file__).resolve().parents[1] / "_sample_orange_bot.pgn"
    txt = sample.read_text(encoding="utf-8")
    info = pgn_info(txt, max_games=50)
    assert info.games >= 1
    assert info.plies_min is None or info.plies_min >= 0
    assert info.plies_max is None or info.plies_max >= 0
    if info.plies_min is not None and info.plies_max is not None:
        assert info.plies_min <= info.plies_max
