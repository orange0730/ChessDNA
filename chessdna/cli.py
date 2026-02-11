import argparse


def main():
    p = argparse.ArgumentParser(prog="chessdna")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Analyze PGN(s) and output report")
    a.add_argument("--pgn", required=True, help="Path to PGN file")

    f = sub.add_parser("fetch", help="Fetch games from Lichess and save PGN")
    f.add_argument("--user", required=True)
    f.add_argument("--max", type=int, default=50)
    f.add_argument("--out", default="games.pgn")

    args = p.parse_args()
    if args.cmd == "fetch":
        raise SystemExit("fetch not implemented yet")
    if args.cmd == "analyze":
        raise SystemExit("analyze not implemented yet")


if __name__ == "__main__":
    main()
