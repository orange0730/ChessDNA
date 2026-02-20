"""Shared settings / defaults for ChessDNA."""

from __future__ import annotations

import os


def default_stockfish_path() -> str:
    """Return the Stockfish binary path.

    Uses the STOCKFISH_PATH env var if set; falls back to a common default.
    """
    return os.environ.get(
        "STOCKFISH_PATH",
        r"D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe",
    )
