from __future__ import annotations

import math
from io import StringIO
from typing import Literal
from pathlib import Path

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

    # Coaching hints (best line from engine at this position)
    bestmove_uci: str | None = None
    pv_uci: list[str] = Field(default_factory=list)


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


class PlayerOverview(BaseModel):
    player_name: str
    games_total: int
    games_found: int

    avg_cpl: float | None = None
    accuracy: float | None = None

    inaccuracy: int = 0
    mistake: int = 0
    blunder: int = 0


class AnalyzeReport(BaseModel):
    games: list[GameReport]
    engine_path: str
    time_per_move: float
    max_plies: int
    player_name: str | None = None
    player_overview: PlayerOverview | None = None


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
    # Server-side guardrails (MVP stability): clamp potentially expensive knobs.
    try:
        time_per_move = float(time_per_move)
    except Exception:
        time_per_move = 0.05
    time_per_move = max(0.01, min(time_per_move, 1.0))

    try:
        max_plies = int(max_plies)
    except Exception:
        max_plies = 200
    max_plies = max(10, min(max_plies, 800))

    pgn_io = StringIO(pgn_text)

    games: list[GameReport] = []

    engine: UciEngine | None = None
    # If Stockfish (or other UCI engine) is not available, degrade gracefully:
    # still parse PGN + SAN/ply list so Web/CLI can run without hard dependency.
    try:
        if engine_path and Path(engine_path).is_file():
            engine = UciEngine(engine_path)
    except Exception:
        engine = None

    # Cross-game player aggregates
    agg_cpls: list[int] = []
    agg_inacc = agg_mis = agg_blun = 0
    games_total = 0
    games_found = 0

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

                san = board.san(move)
                uci = move.uci()

                if engine is not None:
                    # Best eval at current position from side-to-move perspective
                    best_cp, bestmove, pv = engine.eval_position(moves_so_far, movetime_ms=movetime_ms)

                    # Played-move eval in the SAME position (avoid perspective flip issues)
                    played_cp, _played_bestmove, _played_pv = engine.eval_position(
                        moves_so_far,
                        movetime_ms=movetime_ms,
                        searchmoves=[uci],
                    )

                    cpl = max(0, best_cp - played_cp)
                    acc = _lichess_accuracy_from_cpl(cpl)
                    label = _cpl_label(cpl)
                else:
                    best_cp = None
                    bestmove = None
                    pv = []
                    played_cp = None
                    cpl = None
                    acc = None
                    label = "ok"

                # Now advance the game state
                board.push(move)
                moves_so_far.append(uci)

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
                        bestmove_uci=bestmove,
                        pv_uci=pv,
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
                    games_found += 1
                    p_plies = [p for p in plies if p.side == p_side and p.cpl is not None]
                    p_cpls = [p.cpl for p in p_plies if p.cpl is not None]
                    p_avg = sum(p_cpls) / len(p_cpls) if p_cpls else None
                    p_acc = _lichess_accuracy_from_cpl(p_avg) if p_avg is not None else None

                    p_inacc = sum(1 for p in p_plies if p.label == "inaccuracy")
                    p_mis = sum(1 for p in p_plies if p.label == "mistake")
                    p_blun = sum(1 for p in p_plies if p.label == "blunder")

                    p_worst = [p.ply for p in sorted(p_plies, key=lambda x: x.cpl, reverse=True)[:5] if (p.cpl or 0) > 0]

                    # aggregates
                    agg_cpls.extend([int(x) for x in p_cpls])
                    agg_inacc += p_inacc
                    agg_mis += p_mis
                    agg_blun += p_blun

            games_total += 1
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
        if engine is not None:
            engine.quit()

    overview = None
    if player_name:
        avg = (sum(agg_cpls) / len(agg_cpls)) if agg_cpls else None
        acc = _lichess_accuracy_from_cpl(avg) if avg is not None else None
        overview = PlayerOverview(
            player_name=player_name,
            games_total=games_total,
            games_found=games_found,
            avg_cpl=avg,
            accuracy=acc,
            inaccuracy=agg_inacc,
            mistake=agg_mis,
            blunder=agg_blun,
        )

    return AnalyzeReport(
        games=games,
        engine_path=engine_path,
        time_per_move=time_per_move,
        max_plies=max_plies,
        player_name=player_name,
        player_overview=overview,
    )
