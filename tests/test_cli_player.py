from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_analyze_supports_player_flag(tmp_path: Path):
    # Arrange
    repo_root = Path(__file__).resolve().parents[1]
    sample_pgn = repo_root / "_sample_orange_bot.pgn"
    assert sample_pgn.exists()

    out = tmp_path / "report.json"

    # Act: run CLI as a module (uses installed deps in the same env running pytest)
    # Use --engine "" to force engine-less mode (should still compute player_side + games_found).
    cmd = [
        sys.executable,
        "-m",
        "chessdna",
        "analyze",
        "--pgn",
        str(sample_pgn),
        "--engine",
        "",
        "--player",
        "orange_bot",
        "--max-plies",
        "40",
        "--out",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"

    # Assert
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["player_name"] == "orange_bot"
    assert data["player_overview"] is not None
    assert data["player_overview"]["games_found"] >= 1

    # The first game in the sample has orange_bot as Black
    assert data["games"][0]["player_side"] == "black"
