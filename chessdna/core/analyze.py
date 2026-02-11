from __future__ import annotations

import math
from io import StringIO
from typing import Literal

import chess
import chess.pgn
from pydantic import BaseModel, Field

from .uci import UciEngine


class PlyReport(BaseModel):
    ply: int
    san: str
    uci: str
    side: Literal["white", "black"]

    best_cp: int | None = None
    played_cp: int | None = None
    cpl: int | None = None
    accuracy: float | None = None
    label: Literal["ok", "inaccuracy", "mistake", "blunder"] = "ok"


class GameReport(BaseModel):
    headers: dict[str, str] = Field(default_factory=dict)
    plies: list[PlyReport]

    avg_cpl_white: float | None = None
    avg_cpl_black: float | None = None
    accuracy_white: float | None = None
    accuracy_black: float | None = None

    # Turning points: biggest CPL moves in this game (by ply index)
    turning_points: list[int] = Field(default_factory=list)

    # If player_name specified, compute per-game stats for that player only.
    player_side: Literal["white", "black"] | None = None
    player_avg_cpl: float | None = None
    player_accuracy: float | None = None

    player_inaccuracy: int = 0
    player_mistake: int = 0
    player_blunder: int = 0
    player_worst: list[int] = Field(default_factory=list)  # ply numbers


class AnalyzeReport(BaseModel):
    games: list[GameReport]
    engine_path: str
    time_per_move: float
    max_plies: int
    player_name: str | None = None


def _cpl_label(cpl: int) -> str:
    if cpl >= 300:
        return "blunder"
    if cpl >= 100:
        return "mistake"
    if cpl >= 50:
        return "inaccuracy"
    return "ok"


def _lichess_accuracy_from_cpl(cpl: float) -> float:
    # Commonly used approximation of Lichess accuracy mapping.
    # accuracy = 103.1668 * exp(-0.04354*cpl) - 3.1669
    a = 103.1668 * math.exp(-0.04354 * max(0.0, cpl)) - 3.1669
    return float(max(0.0, min(100.0, a)))


def analyze_pgn_text(
    pgn_text: str,
    *,
    engine_path: str,
    time_per_move: float = 0.05,
    max_plies: int = 200,
    player_name: str | None = None,
) -> AnalyzeReport:
    pgn_io = StringIO(pgn_text)

    games: list[GameReport] = []

    engine = UciEngine(engine_path)
    try:
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break

            board = game.board()
            plies: list[PlyReport] = []
            moves_so_far: list[str] = []

            ply_idx = 0
            for move in game.mainline_moves():
                if ply_idx >= max_plies:
                    break

                side = "white" if board.turn == chess.WHITE else "black"
                movetime_ms = max(10, int(time_per_move * 1000))

                # Best eval at current position from side-to-move perspective
                best_cp, _ = engine.eval_position(moves_so_far, movetime_ms=movetime_ms)

                san = board.san(move)
                uci = move.uci()

                # Played-move eval in the SAME position (avoid perspective flip issues)
                played_cp, _ = engine.eval_position(
                    moves_so_far,
                    movetime_ms=movetime_ms,
                    searchmoves=[uci],
                )

                # Now advance the game state
                board.push(move)
                moves_so_far.append(uci)

                cpl = max(0, best_cp - played_cp)
                acc = _lichess_accuracy_from_cpl(cpl)
                label = _cpl_label(cpl)

                plies.append(
                    PlyReport(
                        ply=ply_idx + 1,
                        san=san,
                        uci=uci,
                        side=side,
                        best_cp=best_cp,
                        played_cp=played_cp,
                        cpl=cpl,
                        accuracy=acc,
                        label=label,  # type: ignore[arg-type]
                    )
                )

                ply_idx += 1

            cpls_w = [p.cpl for p in plies if p.side == "white" and p.cpl is not None]
            cpls_b = [p.cpl for p in plies if p.side == "black" and p.cpl is not None]
            avg_w = sum(cpls_w) / len(cpls_w) if cpls_w else None
            avg_b = sum(cpls_b) / len(cpls_b) if cpls_b else None

            acc_w = _lichess_accuracy_from_cpl(avg_w) if avg_w is not None else None
            acc_b = _lichess_accuracy_from_cpl(avg_b) if avg_b is not None else None

            # Turning points: top 5 CPL moves (any side)
            tp = sorted(
                [p for p in plies if p.cpl is not None],
                key=lambda x: x.cpl,
                reverse=True,
            )[:5]
            turning_points = [p.ply for p in tp if (p.cpl or 0) > 0]

            headers = dict(game.headers)

            # Player-specific stats (optional)
            p_side = None
            p_avg = None
            p_acc = None
            p_inacc = p_mis = p_blun = 0
            p_worst: list[int] = []

            if player_name:
                w = headers.get("White")
                b = headers.get("Black")
                if w == player_name:
                    p_side = "white"
                elif b == player_name:
                    p_side = "black"

                if p_side:
                    p_plies = [p for p in plies if p.side == p_side and p.cpl is not None]
                    p_cpls = [p.cpl for p in p_plies if p.cpl is not None]
                    p_avg = sum(p_cpls) / len(p_cpls) if p_cpls else None
                    p_acc = _lichess_accuracy_from_cpl(p_avg) if p_avg is not None else None

                    p_inacc = sum(1 for p in p_plies if p.label == "inaccuracy")
                    p_mis = sum(1 for p in p_plies if p.label == "mistake")
                    p_blun = sum(1 for p in p_plies if p.label == "blunder")

                    p_worst = [p.ply for p in sorted(p_plies, key=lambda x: x.cpl, reverse=True)[:5] if (p.cpl or 0) > 0]

            games.append(
                GameReport(
                    headers=headers,
                    plies=plies,
                    avg_cpl_white=avg_w,
                    avg_cpl_black=avg_b,
                    accuracy_white=acc_w,
                    accuracy_black=acc_b,
                    turning_points=turning_points,
                    player_side=p_side,
                    player_avg_cpl=p_avg,
                    player_accuracy=p_acc,
                    player_inaccuracy=p_inacc,
                    player_mistake=p_mis,
                    player_blunder=p_blun,
                    player_worst=p_worst,
                )
            )

    finally:
        engine.quit()

    return AnalyzeReport(
        games=games,
        engine_path=engine_path,
        time_per_move=time_per_move,
        max_plies=max_plies,
        player_name=player_name,
    )
