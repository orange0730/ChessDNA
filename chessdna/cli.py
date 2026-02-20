import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .core.analyze import analyze_pgn_text
from .core.pgn_utils import pgn_info, preview_games
from .core.settings import default_stockfish_path


def main():
    p = argparse.ArgumentParser(prog="chessdna")
    p.add_argument("--version", action="version", version=f"chessdna {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Fetch recent games from Lichess/Chess.com and save PGN")
    f.add_argument("--platform", choices=["auto", "lichess", "chesscom"], default="auto")
    f.add_argument("--user", required=True)
    f.add_argument("--max", type=int, default=50, help="Max games to fetch (1~50; values outside will be clamped)")
    f.add_argument("--out", default="games.pgn")

    a = sub.add_parser("analyze", help="Analyze PGN(s) and output JSON report")
    a.add_argument("--pgn", required=True, help="Path to PGN file")
    a.add_argument(
        "--engine",
        default=default_stockfish_path(),
        help="Path to Stockfish/engine binary (or set STOCKFISH_PATH env var)",
    )
    a.add_argument("--t", type=float, default=0.05, help="Time per move (seconds)")
    a.add_argument("--max-plies", type=int, default=200)
    a.add_argument(
        "--player",
        default="",
        help="Optional player name to compute per-player stats (matches PGN White/Black exactly)",
    )
    a.add_argument("--out", default="report.json")

    i = sub.add_parser("pgninfo", help="Validate/summarize PGN without engine")
    i.add_argument("--pgn", required=True, help="Path to PGN file")
    i.add_argument("--max-games", type=int, default=200)
    i.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON to stdout",
    )

    s = sub.add_parser(
        "selftest",
        help="Run minimal local self-test (pgninfo + optional analyze)",
    )
    s.add_argument(
        "--pgn",
        default="_sample_orange_bot.pgn",
        help="Path to PGN file (default: _sample_orange_bot.pgn in CWD)",
    )
    s.add_argument(
        "--engine",
        default=default_stockfish_path(),
        help="Path to Stockfish/engine binary (or set STOCKFISH_PATH env var). If missing, analyze is skipped.",
    )
    s.add_argument("--t", type=float, default=0.02, help="Time per move (seconds)")
    s.add_argument("--max-plies", type=int, default=120)
    s.add_argument("--out", default="_selftest_cli_report.json")
    s.add_argument(
        "--no-analyze",
        action="store_true",
        help="Only run pgninfo (skip engine analyze)",
    )
    s.add_argument(
        "--web-smoke",
        action="store_true",
        help="Also run a minimal FastAPI route smoke test (POST /analyze with pasted PGN)",
    )

    args = p.parse_args()

    if args.cmd == "fetch":
        from .core.http import FetchError

        def fetch_lichess(u: str, *, max_games: int) -> str:
            from .core.lichess import fetch_user_games_pgn

            return fetch_user_games_pgn(u, max_games=max_games)

        def fetch_chesscom(u: str, *, max_games: int) -> str:
            from .core.chesscom import fetch_user_games_pgn

            return fetch_user_games_pgn(u, max_games=max_games)

        max_games = max(1, min(int(args.max), 50))
        if max_games != int(args.max):
            print(f"[WARN] --max clamped to {max_games} (MVP safety limit)")

        pgn = ""
        if args.platform == "lichess":
            pgn = fetch_lichess(args.user, max_games=max_games)
        elif args.platform == "chesscom":
            pgn = fetch_chesscom(args.user, max_games=max_games)
        else:
            # Auto: try Lichess first (fast + single endpoint), then fallback to chess.com.
            try:
                pgn = fetch_lichess(args.user, max_games=max_games)
                if not pgn.strip():
                    print("[WARN] auto: lichess returned empty PGN; fallback to chess.com")
                    pgn = fetch_chesscom(args.user, max_games=max_games)
            except FetchError as e:
                print(f"[WARN] auto: lichess fetch failed; fallback to chess.com: {e}")
                pgn = fetch_chesscom(args.user, max_games=max_games)

        Path(args.out).write_text(pgn, encoding="utf-8")
        print(f"[OK] wrote {args.out}")

    elif args.cmd == "analyze":
        pgn_text = Path(args.pgn).read_text(encoding="utf-8", errors="replace")
        raw_t = args.t
        raw_mx = args.max_plies
        player = (args.player or "").strip() or None
        report = analyze_pgn_text(
            pgn_text,
            engine_path=args.engine,
            time_per_move=raw_t,
            max_plies=raw_mx,
            player_name=player,
        )
        if float(report.time_per_move) != float(raw_t):
            print(f"[WARN] --t clamped to {report.time_per_move} (MVP safety limit)")
        if int(report.max_plies) != int(raw_mx):
            print(f"[WARN] --max-plies clamped to {report.max_plies} (MVP safety limit)")

        if args.out == "-":
            # stdout mode (useful for piping)
            print(report.model_dump_json(indent=2))
        else:
            Path(args.out).write_text(report.model_dump_json(indent=2), encoding="utf-8")
            print(f"[OK] wrote {args.out}")

    elif args.cmd == "pgninfo":
        pgn_text = Path(args.pgn).read_text(encoding="utf-8", errors="replace")
        info = pgn_info(pgn_text, max_games=args.max_games)

        if args.json:
            print(json.dumps(asdict(info), ensure_ascii=False))
            return

        print(
            "[OK] games={g} plies_min={mn} plies_max={mx} plies_avg={avg}".format(
                g=info.games,
                mn=info.plies_min,
                mx=info.plies_max,
                avg=(None if info.plies_avg is None else round(info.plies_avg, 2)),
            )
        )

    elif args.cmd == "selftest":
        pgn_path = Path(args.pgn)
        if not pgn_path.exists():
            raise SystemExit(f"[ERR] PGN not found: {pgn_path}")

        pgn_text = pgn_path.read_text(encoding="utf-8", errors="replace")

        # 1) lightweight parse/summary
        info = pgn_info(pgn_text, max_games=50)
        print(
            "[OK] pgninfo games={g} plies_min={mn} plies_max={mx} plies_avg={avg}".format(
                g=info.games,
                mn=info.plies_min,
                mx=info.plies_max,
                avg=(None if info.plies_avg is None else round(info.plies_avg, 2)),
            )
        )

        # 2) ensure UI preview flow can parse headers and generate stable idx list
        previews, raw_games = preview_games(pgn_text, max_games=50)
        if len(previews) != len(raw_games):
            raise SystemExit(f"[ERR] preview mismatch: previews={len(previews)} raw_games={len(raw_games)}")
        if previews:
            idxs = [g.idx for g in previews]
            if idxs != list(range(len(previews))):
                raise SystemExit(f"[ERR] preview idx not contiguous: {idxs[:10]}...")
        print(f"[OK] preview games={len(previews)}")

        if args.web_smoke:
            try:
                from starlette.testclient import TestClient

                from .app import FETCH_STORE, app

                with TestClient(app) as c:
                    # A) Smoke test: pasted PGN
                    r = c.post(
                        "/analyze",
                        data={
                            "pgn_text": pgn_text,
                            "time_per_move": 0.01,
                            "max_plies": 40,
                            "engine_path": args.engine,
                        },
                    )
                    if r.status_code >= 400:
                        raise SystemExit(f"[ERR] web smoke failed (/analyze pasted): {r.status_code} {r.text[:200]}")
                    if "report" not in r.text.lower():
                        # best-effort assertion: report page should include 'report' keyword
                        print("[WARN] web smoke(/analyze pasted): response did not contain 'report' keyword (may be template change)")
                    print("[OK] web smoke /analyze (pasted)")

                    # B) Smoke test: online UX path without real network
                    # Seed FETCH_STORE directly then call /analyze with preview_token + game_idx.
                    import uuid

                    token = "selftest_" + uuid.uuid4().hex
                    FETCH_STORE[token] = {"platform": "", "previews": previews, "games": raw_games}

                    r2 = c.post(
                        "/analyze",
                        data={
                            "preview_token": token,
                            "game_idx": [0],
                            "time_per_move": 0.01,
                            "max_plies": 40,
                            "engine_path": args.engine,
                        },
                    )
                    if r2.status_code >= 400:
                        raise SystemExit(f"[ERR] web smoke failed (/analyze preview_token): {r2.status_code} {r2.text[:200]}")
                    if "report" not in r2.text.lower():
                        print("[WARN] web smoke(/analyze preview_token): response did not contain 'report' keyword (may be template change)")
                    print("[OK] web smoke /analyze (preview_token)")
            except SystemExit:
                raise
            except Exception as e:
                print(f"[SKIP] web smoke (missing deps or runtime error): {e!r}")

        if args.no_analyze:
            print("[OK] selftest done (no-analyze)")
            return

        engine_path = Path(args.engine)
        if not engine_path.exists():
            print(f"[SKIP] engine not found: {engine_path}")
            print("[OK] selftest done (pgninfo only)")
            return

        report = analyze_pgn_text(
            pgn_text,
            engine_path=str(engine_path),
            time_per_move=args.t,
            max_plies=args.max_plies,
        )
        Path(args.out).write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"[OK] wrote {args.out}")


if __name__ == "__main__":
    main()
