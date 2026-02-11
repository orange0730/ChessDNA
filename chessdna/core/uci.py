from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Iterable


@dataclass
class UciScore:
    kind: str  # 'cp' | 'mate'
    value: int


def _parse_score(tokens: list[str]) -> UciScore | None:
    # tokens after 'score'
    if len(tokens) < 2:
        return None
    t, v = tokens[0], tokens[1]
    try:
        iv = int(v)
    except ValueError:
        return None
    if t in ("cp", "mate"):
        return UciScore(t, iv)
    return None


class UciEngine:
    """Minimal synchronous UCI driver (avoids asyncio issues on Windows)."""

    def __init__(self, path: str):
        self.path = path
        self.p = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert self.p.stdin and self.p.stdout
        self._handshake()

    def _send(self, line: str) -> None:
        assert self.p.stdin
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def _readline(self) -> str:
        assert self.p.stdout
        line = self.p.stdout.readline()
        if line == "":
            raise RuntimeError("engine stdout closed")
        return line.rstrip("\r\n")

    def _handshake(self) -> None:
        self._send("uci")
        while True:
            line = self._readline()
            if line == "uciok":
                break
        self._send("isready")
        while True:
            line = self._readline()
            if line == "readyok":
                break

    def quit(self) -> None:
        try:
            self._send("quit")
        except Exception:
            pass
        try:
            self.p.terminate()
        except Exception:
            pass

    def eval_position(self, moves_uci: list[str], *, movetime_ms: int) -> tuple[int, str]:
        """Return (score_cp_from_side_to_move, bestmove_uci)."""
        # Use startpos to keep it simple for standard chess.
        if moves_uci:
            self._send("position startpos moves " + " ".join(moves_uci))
        else:
            self._send("position startpos")

        self._send(f"go movetime {movetime_ms}")

        last_score: UciScore | None = None
        bestmove = "0000"

        while True:
            line = self._readline()
            if line.startswith("info "):
                # Find "score cp X" or "score mate X" anywhere
                m = re.search(r"\bscore\s+(cp|mate)\s+(-?\d+)", line)
                if m:
                    last_score = UciScore(m.group(1), int(m.group(2)))
            elif line.startswith("bestmove "):
                parts = line.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                break

        # Convert to centipawn-ish for comparisons
        if last_score is None:
            score_cp = 0
        elif last_score.kind == "cp":
            score_cp = last_score.value
        else:
            # mate N: map to huge cp preserving sign
            sign = 1 if last_score.value > 0 else -1 if last_score.value < 0 else 0
            score_cp = sign * (100000 - 1000 * abs(last_score.value))

        return score_cp, bestmove
