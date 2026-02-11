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
        },
    )


@app.get("/download/{report_id}/{kind}")
def download(report_id: str, kind: str):
    if kind not in ("json", "html"):
        raise HTTPException(status_code=400, detail="kind must be json or html")
    return download_file(REPORT_STORE, report_id, kind)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    pgn: UploadFile | None = File(None),
    pgn_text: str = Form(""),
    lichess_user: str = Form(""),
    chesscom_user: str = Form(""),
    fetch_max: int = Form(10),
    player_name: str = Form(""),
    engine_path: str = Form(default_stockfish_path()),
    time_per_move: float = Form(0.05),
    max_plies: int = Form(200),
):
    # Prefer pasted text, then online fetch, then uploaded file
    src = (pgn_text or "").strip()

    lichess_user = (lichess_user or "").strip()
    chesscom_user = (chesscom_user or "").strip()

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
