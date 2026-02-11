from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


def _get_json(url: str) -> Any:
    r = requests.get(url, timeout=60, headers={"User-Agent": "ChessDNA/0.1"})
    r.raise_for_status()
    return r.json()


def fetch_user_games_pgn(username: str, *, max_games: int = 50) -> str:
    """Fetch recent games from chess.com PubAPI and return concatenated PGN.

    Uses archives endpoint to discover monthly archives, then pulls games and
    concatenates their 'pgn' fields.
    """
    u = username.lower()
    archives_url = f"https://api.chess.com/pub/player/{u}/games/archives"
    data = _get_json(archives_url)
    archives: list[str] = list(data.get("archives", []))
    if not archives:
        return ""

    # newest first
    archives = list(reversed(archives))

    pgns: list[str] = []
    for a in archives:
        if len(pgns) >= max_games:
            break
        month = _get_json(a)
        games = month.get("games", [])
        # games already newest->oldest? not guaranteed; keep as provided.
        for g in games:
            if len(pgns) >= max_games:
                break
            p = g.get("pgn")
            if p:
                pgns.append(p.strip())

    return "\n\n".join(pgns) + ("\n" if pgns else "")
