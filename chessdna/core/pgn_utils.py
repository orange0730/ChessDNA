from __future__ import annotations

import io
from dataclasses import dataclass

import chess.pgn


@dataclass
class GamePreview:
    idx: int
    white: str
    black: str
    result: str
    date: str
    event: str
    site: str


def _safe(h: dict, key: str) -> str:
    v = (h.get(key) or "").strip()
    return v


def split_pgn_games(pgn_text: str, *, max_games: int | None = None) -> list[str]:
    """Split concatenated PGN into per-game PGN strings.

    Uses python-chess PGN reader for robustness.
    """
    pgn_text = (pgn_text or "").strip()
    if not pgn_text:
        return []

    out: list[str] = []
    f = io.StringIO(pgn_text)
    while True:
        game = chess.pgn.read_game(f)
        if game is None:
            break
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        s = game.accept(exporter).strip()
        if s:
            out.append(s + "\n")
        if max_games is not None and len(out) >= max_games:
            break

    return out


def preview_games(pgn_text: str, *, max_games: int = 200) -> tuple[list[GamePreview], list[str]]:
    """Return (previews, raw_games) for UI selection."""
    raw_games = split_pgn_games(pgn_text, max_games=max_games)

    previews: list[GamePreview] = []
    for i, gtxt in enumerate(raw_games):
        f = io.StringIO(gtxt)
        game = chess.pgn.read_game(f)
        if game is None:
            continue
        h = game.headers
        previews.append(
            GamePreview(
                idx=i,
                white=_safe(h, "White") or "?",
                black=_safe(h, "Black") or "?",
                result=_safe(h, "Result") or "*",
                date=_safe(h, "UTCDate") or _safe(h, "Date") or "?",
                event=_safe(h, "Event") or "?",
                site=_safe(h, "Site") or "?",
            )
        )

    return previews, raw_games
