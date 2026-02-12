import os
import sys
import tempfile
from pathlib import Path
import uuid

import asyncio
import anyio
from functools import partial

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .core.analyze import analyze_pgn_text
from .routes_downloads import download_file


# Ensure subprocess support in engine analysis (python-chess uses asyncio internally).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def default_stockfish_path() -> str:
    # Reasonable default for this machine; can be overridden by env var.
    return os.environ.get(
        "STOCKFISH_PATH",
        r"D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe",
    )


app = FastAPI(title="ChessDNA", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory report store (MVP). Maps report_id -> {json_path, html_path}
REPORT_STORE: dict[str, dict[str, str]] = {}
REPORT_TMP_DIR = Path(tempfile.gettempdir()) / "chessdna_reports"
REPORT_TMP_DIR.mkdir(exist_ok=True)

# In-memory fetched PGN store (MVP). Maps token -> {"platform": str, "previews": [...], "games": [pgn_str...]}
# Best-effort persistence: we also write the fetched concatenated PGN to a temp file
# so the preview_token can sometimes survive a server restart.
FETCH_STORE: dict[str, dict[str, object]] = {}
FETCH_TMP_DIR = Path(tempfile.gettempdir()) / "chessdna_fetch"
FETCH_TMP_DIR.mkdir(exist_ok=True)

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_engine": default_stockfish_path(),
            "default_time": 0.05,
            "preview_token": "",
            "games": [],
        },
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    request: Request,
    lichess_user: str = Form(""),
    chesscom_user: str = Form(""),
    fetch_max: int = Form(10),
):
    """Fetch recent games and show a selectable list (MVP UX step)."""

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

    try:
        fetch_max = int(fetch_max)
    except Exception:
        fetch_max = 10
    fetch_max = max(1, min(fetch_max, 50))

    src = ""
    platform = ""
    try:
        if lichess_user:
            from .core.lichess import fetch_user_games_pgn as fetch_lichess

            src = fetch_lichess(lichess_user, max_games=fetch_max).strip()
            platform = "lichess"
        elif chesscom_user:
            from .core.chesscom import fetch_user_games_pgn as fetch_chesscom

            src = fetch_chesscom(chesscom_user, max_games=fetch_max).strip()
            platform = "chesscom"
    except Exception as e:
        import traceback

        return TEMPLATES.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": repr(e),
                "trace": traceback.format_exc(),
                "engine_path": default_stockfish_path(),
                "hint": "線上抓取失敗：可能是 username 不存在 / API 限流 / 網路問題。",
            },
            status_code=500,
        )

    if not src:
        return TEMPLATES.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "ValueError('Empty PGN from online fetch')",
                "trace": "",
                "engine_path": default_stockfish_path(),
                "hint": "抓不到棋譜：請確認 username 是否正確，且帳號對局是公開的。",
            },
            status_code=400,
        )

    from .core.pgn_utils import preview_games

    previews, raw_games = preview_games(src, max_games=fetch_max)

    token = uuid.uuid4().hex
    FETCH_STORE[token] = {"platform": platform, "previews": previews, "games": raw_games}

    # Persist raw PGN for best-effort reload after restart.
    try:
        (FETCH_TMP_DIR / f"{token}.pgn").write_text(src, encoding="utf-8")
    except Exception:
        pass

    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_engine": default_stockfish_path(),
            "default_time": 0.05,
            "preview_token": token,
            "games": previews,
            "prefill": {
                "lichess_user": lichess_user,
                "chesscom_user": chesscom_user,
                "fetch_max": fetch_max,
            },
        },
    )


@app.get("/download/{report_id}/{kind}")
def download(report_id: str, kind: str):
    if kind not in ("json", "html"):
        raise HTTPException(status_code=400, detail="kind must be json or html")
    # Best-effort: after restart, REPORT_STORE is empty, but temp artifacts may still exist.
    return download_file(REPORT_STORE, report_id, kind, fallback_dir=REPORT_TMP_DIR)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    pgn: UploadFile | None = File(None),
    pgn_text: str = Form(""),
    lichess_user: str = Form(""),
    chesscom_user: str = Form(""),
    fetch_max: int = Form(10),
    preview_token: str = Form(""),
    game_idx: list[int] = Form([]),
    player_name: str = Form(""),
    engine_path: str = Form(default_stockfish_path()),
    time_per_move: float = Form(0.05),
    max_plies: int = Form(200),
):
    # Source priority:
    # 1) preview_token + selected game_idx (online list->select UX)
    # 2) pasted pgn_text
    # 3) online fetch by username
    # 4) uploaded file

    preview_token = (preview_token or "").strip()

    src = ""
    if preview_token:
        store = FETCH_STORE.get(preview_token)
        if not store:
            # Best-effort reload from temp (in case of server restart).
            try:
                p = FETCH_TMP_DIR / f"{preview_token}.pgn"
                if p.exists():
                    src2 = p.read_text(encoding="utf-8", errors="replace")
                    from .core.pgn_utils import preview_games

                    previews2, raw_games2 = preview_games(src2, max_games=fetch_max)
                    store = {"platform": "", "previews": previews2, "games": raw_games2}
                    FETCH_STORE[preview_token] = store
            except Exception:
                store = None

        if not store:
            return TEMPLATES.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "ValueError('preview_token expired')",
                    "trace": "",
                    "engine_path": engine_path,
                    "hint": "這個預覽 token 已失效（伺服器重啟或時間過久）。請回到首頁重新抓取棋譜。",
                },
                status_code=400,
            )

        games = list(store.get("games") or [])
        previews = list(store.get("previews") or [])

        selected = sorted(set(int(x) for x in (game_idx or [])))
        if not selected:
            # No selection: re-render index with list
            return TEMPLATES.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "default_engine": default_stockfish_path(),
                    "default_time": 0.05,
                    "preview_token": preview_token,
                    "games": previews,
                    "inline_err": "請先勾選要分析的對局（至少 1 盤）。",
                },
                status_code=400,
            )

        chosen: list[str] = []
        for i in selected:
            if 0 <= i < len(games):
                chosen.append(str(games[i]).strip())
        src = "\n\n".join([c for c in chosen if c]).strip()

    if not src:
        src = (pgn_text or "").strip()

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

    # Stability guardrails for MVP: avoid huge fetches that make the server hang.
    try:
        fetch_max = int(fetch_max)
    except Exception:
        fetch_max = 10
    fetch_max = max(1, min(fetch_max, 50))

    if not src and lichess_user:
        from .core.lichess import fetch_user_games_pgn as fetch_lichess

        src = fetch_lichess(lichess_user, max_games=fetch_max).strip()

    if not src and chesscom_user:
        from .core.chesscom import fetch_user_games_pgn as fetch_chesscom

        src = fetch_chesscom(chesscom_user, max_games=fetch_max).strip()

    if not src and pgn is not None:
        src = (await pgn.read()).decode("utf-8", errors="replace").strip()

    if not src:
        return TEMPLATES.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "ValueError('Missing PGN: please upload a file / paste PGN / or provide online username')",
                "trace": "",
                "engine_path": engine_path,
                "hint": "請上傳 PGN 檔、貼上 PGN 文字，或輸入 Lichess/Chess.com username。",
            },
            status_code=400,
        )

    player_name = player_name.strip() or None

    try:
        # Run CPU/IO-heavy engine analysis in a worker thread to avoid
        # asyncio event-loop/subprocess quirks on Windows.
        fn = partial(
            analyze_pgn_text,
            src,
            engine_path=engine_path,
            time_per_move=time_per_move,
            max_plies=max_plies,
            player_name=player_name,
        )
        report = await anyio.to_thread.run_sync(fn)

        # Write report artifacts to temp and expose download links.
        report_id = uuid.uuid4().hex
        json_path = str(REPORT_TMP_DIR / f"{report_id}.json")
        html_path = str(REPORT_TMP_DIR / f"{report_id}.html")

        Path(json_path).write_text(report.model_dump_json(indent=2), encoding="utf-8")

        # Render HTML to string for download
        tpl = TEMPLATES.get_template("report.html")
        html = tpl.render({"request": request, "report": report, "debug_path": json_path, "report_id": report_id})
        Path(html_path).write_text(html, encoding="utf-8")

        REPORT_STORE[report_id] = {"json": json_path, "html": html_path}

        return TEMPLATES.TemplateResponse(
            "report.html",
            {"request": request, "report": report, "debug_path": json_path, "report_id": report_id},
        )

    except Exception as e:
        import traceback

        # Show a friendly error page instead of a raw 500.
        return TEMPLATES.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": repr(e),
                "trace": traceback.format_exc(),
                "engine_path": engine_path,
                "hint": "常見原因：Stockfish 路徑錯誤 / PGN 內容格式異常 / 檔案不是 UTF-8。",
            },
            status_code=500,
        )
