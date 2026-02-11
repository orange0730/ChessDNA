from __future__ import annotations

import requests


def fetch_user_games_pgn(username: str, *, max_games: int = 50) -> str:
    """Fetch recent games as a single PGN string (public, no auth required)."""
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        "max": str(max_games),
        "pgnInJson": "false",
        "clocks": "true",
        "evals": "false",
        "opening": "true",
        "moves": "true",
    }
    headers = {"Accept": "application/x-chess-pgn"}
    r = requests.get(url, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    return r.text
