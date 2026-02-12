import os
import sys
import tempfile
from pathlib import Path
import time
import uuid

import asyncio
import anyio
from functools import partial
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avoid leaking disk space over long-running dev sessions.
    # Configurable via env vars; defaults are conservative.
    try:
        report_hours = float(os.environ.get("CHESSDNA_REPORT_TMP_MAX_AGE_HOURS", "168"))  # 7 days
    except Exception:
        report_hours = 168.0

    try:
        fetch_hours = float(os.environ.get("CHESSDNA_FETCH_TMP_MAX_AGE_HOURS", "48"))  # 2 days
    except Exception:
        fetch_hours = 48.0

    _cleanup_tmp_dir(REPORT_TMP_DIR, max_age_hours=report_hours, suffixes=(".json", ".html"))
    _cleanup_tmp_dir(FETCH_TMP_DIR, max_age_hours=fetch_hours, suffixes=(".pgn",))

    yield


app = FastAPI(title="ChessDNA", version="0.1.0", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory report store (MVP). Maps report_id -> {json_path, html_path}
REPORT_STORE: dict[str, dict[str, str]] = {}
REPORT_TMP_DIR = Path(tempfile.gettempdir()) / "chessdna_reports"
REPORT_TMP_DIR.mkdir(exist_ok=True)


def _cleanup_tmp_dir(tmp_dir: Path, *, max_age_hours: float, suffixes: tuple[str, ...]) -> int:
    """Best-effort cleanup for temp artifacts.

    Keeps the MVP behavior (write artifacts to temp), but prevents unbounded
    growth over time.

    Returns number of deleted files.
    """

    now = time.time()
    max_age_s = max_age_hours * 3600.0
    deleted = 0

    try:
        for p in tmp_dir.glob("*"):
            if not p.is_file():
                continue
            if suffixes and p.suffix.lower() not in suffixes:
                continue
            try:
                st = p.stat()
                age = now - float(st.st_mtime)
                if age > max_age_s:
                    p.unlink(missing_ok=True)
                    deleted += 1
            except Exception:
                # Best-effort: ignore individual file errors.
                pass
    except Exception:
        pass

    return deleted

# In-memory fetched PGN store (MVP). Maps token -> {"platform": str, "previews": [...], "games": [pgn_str...]}
# Best-effort persistence: we also write the fetched concatenated PGN to a temp file
# so the preview_token can sometimes survive a server restart.
FETCH_STORE: dict[str, dict[str, object]] = {}
FETCH_TMP_DIR = Path(tempfile.gettempdir()) / "chessdna_fetch"
FETCH_TMP_DIR.mkdir(exist_ok=True)


# startup housekeeping moved to FastAPI lifespan

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
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
    platform: str = Form("auto"),
    lichess_user: str = Form(""),
    chesscom_user: str = Form(""),
    fetch_max: int = Form(10),
):
    """Fetch recent games and show a selectable list (MVP UX step)."""

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

    raw_fetch_max = fetch_max
    try:
        fetch_max = int(fetch_max)
    except Exception:
        fetch_max = 10
    fetch_max = max(1, min(fetch_max, 50))

    inline_warn = ""
    try:
        if int(raw_fetch_max) != int(fetch_max):
            inline_warn = f"fetch_max 已限制為 {fetch_max}（MVP 安全上限 50）"
    except Exception:
        # raw_fetch_max might be non-numeric; keep quiet.
        pass

    req_platform = (platform or "auto").strip().lower()
    if req_platform not in ("auto", "lichess", "chesscom"):
        req_platform = "auto"

    # If user explicitly selects a platform, require its username.
    # Also guard the auto case server-side (client JS blocks this, but don't rely on it).
    if req_platform == "auto" and (not lichess_user) and (not chesscom_user):
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "default_engine": default_stockfish_path(),
                "default_time": 0.05,
                "preview_token": "",
                "games": [],
                "inline_warn": inline_warn,
                "inline_err": "要列出對局，請先輸入 Lichess 或 Chess.com username。",
                "prefill": {
                    "platform": req_platform,
                    "lichess_user": lichess_user,
                    "chesscom_user": chesscom_user,
                    "fetch_max": fetch_max,
                },
            },
            status_code=400,
        )

    if req_platform == "lichess" and not lichess_user:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "default_engine": default_stockfish_path(),
                "default_time": 0.05,
                "preview_token": "",
                "games": [],
                "inline_warn": inline_warn,
                "inline_err": "你選了 Lichess，但沒有輸入 Lichess username。",
                "prefill": {
                    "platform": req_platform,
                    "lichess_user": lichess_user,
                    "chesscom_user": chesscom_user,
                    "fetch_max": fetch_max,
                },
            },
            status_code=400,
        )

    if req_platform == "chesscom" and not chesscom_user:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "default_engine": default_stockfish_path(),
                "default_time": 0.05,
                "preview_token": "",
                "games": [],
                "inline_warn": inline_warn,
                "inline_err": "你選了 Chess.com，但沒有輸入 Chess.com username。",
                "prefill": {
                    "platform": req_platform,
                    "lichess_user": lichess_user,
                    "chesscom_user": chesscom_user,
                    "fetch_max": fetch_max,
                },
            },
            status_code=400,
        )

    src = ""
    used_platform = ""
    try:
        if req_platform == "lichess" or (req_platform == "auto" and lichess_user):
            from .core.lichess import fetch_user_games_pgn as fetch_lichess

            src = fetch_lichess(lichess_user, max_games=fetch_max).strip()
            used_platform = "lichess"
        elif req_platform == "chesscom" or (req_platform == "auto" and chesscom_user):
            from .core.chesscom import fetch_user_games_pgn as fetch_chesscom

            src = fetch_chesscom(chesscom_user, max_games=fetch_max).strip()
            used_platform = "chesscom"
    except Exception as e:
        import traceback

        return TEMPLATES.TemplateResponse(
            request,
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
            request,
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
    FETCH_STORE[token] = {"platform": used_platform, "previews": previews, "games": raw_games}

    # Persist raw PGN for best-effort reload after restart.
    try:
        (FETCH_TMP_DIR / f"{token}.pgn").write_text(src, encoding="utf-8")
    except Exception:
        pass

    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "default_engine": default_stockfish_path(),
            "default_time": 0.05,
            "preview_token": token,
            "games": previews,
            "inline_warn": inline_warn,
            "prefill": {
                "platform": req_platform,
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
    platform: str = Form("auto"),
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

    # Stability guardrails for MVP: avoid huge fetch/preview payloads.
    # Note: this also protects the preview_token reload path (after restart).
    try:
        fetch_max = int(fetch_max)
    except Exception:
        fetch_max = 10
    fetch_max = max(1, min(fetch_max, 50))

    req_platform = (platform or "auto").strip().lower()
    if req_platform not in ("auto", "lichess", "chesscom"):
        req_platform = "auto"

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

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
                request,
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
        if selected:
            chosen: list[str] = []
            for i in selected:
                if 0 <= i < len(games):
                    chosen.append(str(games[i]).strip())
            src = "\n\n".join([c for c in chosen if c]).strip()
        else:
            # If user is in preview mode, require an explicit selection.
            # Otherwise it is easy to accidentally re-fetch and analyze *all* games.
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "request": request,
                    "default_engine": default_stockfish_path(),
                    "default_time": 0.05,
                    "preview_token": preview_token,
                    "games": previews,
                    "inline_err": "你目前在『線上抓棋譜預覽』模式：請至少勾選 1 盤對局後再按『開始分析』。",
                    "prefill": {
                        "platform": req_platform,
                        "lichess_user": lichess_user,
                        "chesscom_user": chesscom_user,
                        "fetch_max": fetch_max,
                    },
                },
                status_code=400,
            )

    if not src:
        src = (pgn_text or "").strip()

    req_platform = (platform or "auto").strip().lower()
    if req_platform not in ("auto", "lichess", "chesscom"):
        req_platform = "auto"

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

    # (fetch_max already clamped above)

    # If user explicitly selects a platform, require its username.
    # (Client-side JS already blocks this, but we also guard server-side.)
    if not src:
        if req_platform == "lichess" and not lichess_user:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "request": request,
                    "default_engine": default_stockfish_path(),
                    "default_time": 0.05,
                    "preview_token": "",
                    "games": [],
                    "inline_err": "你選了 Lichess，但沒有輸入 Lichess username。",
                    "prefill": {
                        "platform": req_platform,
                        "lichess_user": lichess_user,
                        "chesscom_user": chesscom_user,
                        "fetch_max": fetch_max,
                    },
                },
                status_code=400,
            )

        if req_platform == "chesscom" and not chesscom_user:
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "request": request,
                    "default_engine": default_stockfish_path(),
                    "default_time": 0.05,
                    "preview_token": "",
                    "games": [],
                    "inline_err": "你選了 Chess.com，但沒有輸入 Chess.com username。",
                    "prefill": {
                        "platform": req_platform,
                        "lichess_user": lichess_user,
                        "chesscom_user": chesscom_user,
                        "fetch_max": fetch_max,
                    },
                },
                status_code=400,
            )

    if not src and req_platform in ("auto", "lichess") and lichess_user:
        from .core.lichess import fetch_user_games_pgn as fetch_lichess

        src = fetch_lichess(lichess_user, max_games=fetch_max).strip()

    if not src and req_platform in ("auto", "chesscom") and chesscom_user:
        from .core.chesscom import fetch_user_games_pgn as fetch_chesscom

        src = fetch_chesscom(chesscom_user, max_games=fetch_max).strip()

    if not src and pgn is not None:
        src = (await pgn.read()).decode("utf-8", errors="replace").strip()

    if not src:
        return TEMPLATES.TemplateResponse(
            request,
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
            request,
            "report.html",
            {"request": request, "report": report, "debug_path": json_path, "report_id": report_id},
        )

    except Exception as e:
        import traceback

        # Show a friendly error page instead of a raw 500.
        return TEMPLATES.TemplateResponse(
            request,
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
