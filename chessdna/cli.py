import argparse
from pathlib import Path

from .core.analyze import analyze_pgn_text
from .core.lichess import fetch_user_games_pgn
from .core.pgn_utils import pgn_info


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

    i = sub.add_parser("pgninfo", help="Validate/summarize PGN without engine")
    i.add_argument("--pgn", required=True, help="Path to PGN file")
    i.add_argument("--max-games", type=int, default=200)

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
        Path(args.out).write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"[OK] wrote {args.out}")

    if args.cmd == "pgninfo":
        pgn_text = Path(args.pgn).read_text(encoding="utf-8", errors="replace")
        info = pgn_info(pgn_text, max_games=args.max_games)
        print(
            "[OK] games={g} plies_min={mn} plies_max={mx} plies_avg={avg}".format(
                g=info.games,
                mn=info.plies_min,
                mx=info.plies_max,
                avg=(None if info.plies_avg is None else round(info.plies_avg, 2)),
            )
        )


if __name__ == "__main__":
    main()
