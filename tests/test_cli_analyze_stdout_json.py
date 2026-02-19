import json
import subprocess
import sys
from pathlib import Path


def test_cli_analyze_stdout_json(tmp_path: Path):
    # Minimal valid PGN with one short game.
    pgn = """[Event \"Test\"]
[Site \"?\"]
[Date \"2026.02.20\"]
[Round \"-\"]
[White \"White\"]
[Black \"Black\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
"""

    p = tmp_path / "t.pgn"
    p.write_text(pgn, encoding="utf-8")

    missing_engine = tmp_path / "__missing_stockfish__"

    out = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "chessdna",
            "analyze",
            "--pgn",
            str(p),
            "--engine",
            str(missing_engine),
            "--t",
            "0.05",
            "--max-plies",
            "80",
            "--out",
            "-",
        ],
        text=True,
    ).strip()

    data = json.loads(out)
    assert data["games"]
    assert data["time_per_move"] == 0.05
    assert data["max_plies"] == 80
