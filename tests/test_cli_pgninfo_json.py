import json
import subprocess
import sys
from pathlib import Path


def test_cli_pgninfo_json(tmp_path: Path):
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

    out = subprocess.check_output(
        [sys.executable, "-m", "chessdna", "pgninfo", "--pgn", str(p), "--json"],
        text=True,
    ).strip()

    data = json.loads(out)
    assert data["games"] == 1
    assert data["plies_min"] == 6
    assert data["plies_max"] == 6
    assert abs(float(data["plies_avg"]) - 6.0) < 1e-9
