import argparse
from pathlib import Path

from .core.analyze import analyze_pgn_text
from .core.lichess import fetch_user_games_pgn


def main():
    p = argparse.ArgumentParser(prog="chessdna")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Fetch recent games from Lichess and save PGN")
    f.add_argument("--user", required=True)
    f.add_argument("--max", type=int, default=50)
    f.add_argument("--out", default="games.pgn")

    a = sub.add_parser("analyze", help="Analyze PGN(s) and output JSON report")
    a.add_argument("--pgn", required=True, help="Path to PGN file")
    a.add_argument(
        "--engine",
        default=r"D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe",
        help="Path to Stockfish/engine binary",
    )
    a.add_argument("--t", type=float, default=0.05, help="Time per move (seconds)")
    a.add_argument("--max-plies", type=int, default=200)
    a.add_argument("--out", default="report.json")

    args = p.parse_args()

    if args.cmd == "fetch":
        pgn = fetch_user_games_pgn(args.user, max_games=args.max)
        Path(args.out).write_text(pgn, encoding="utf-8")
        print(f"[OK] wrote {args.out}")

    if args.cmd == "analyze":
        pgn_text = Path(args.pgn).read_text(encoding="utf-8", errors="replace")
        report = analyze_pgn_text(
            pgn_text,
            engine_path=args.engine,
            time_per_move=args.t,
            max_plies=args.max_plies,
        )
        Path(args.out).write_text(report.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] wrote {args.out}")


if __name__ == "__main__":
    main()
