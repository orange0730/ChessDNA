import os
import sys
import tempfile
from pathlib import Path

import asyncio
import anyio
from functools import partial
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .core.analyze import analyze_pgn_text


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


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    pgn: UploadFile = File(...),
    engine_path: str = Form(default_stockfish_path()),
    time_per_move: float = Form(0.05),
    max_plies: int = Form(200),
):
    pgn_text = (await pgn.read()).decode("utf-8", errors="replace")

    try:
        # Run CPU/IO-heavy engine analysis in a worker thread to avoid
        # asyncio event-loop/subprocess quirks on Windows.
        fn = partial(
            analyze_pgn_text,
            pgn_text,
            engine_path=engine_path,
            time_per_move=time_per_move,
            max_plies=max_plies,
        )
        report = await anyio.to_thread.run_sync(fn)

        # Also write a copy to a temp file (useful for debugging/demo)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
            debug_path = f.name

        return TEMPLATES.TemplateResponse(
            "report.html",
            {"request": request, "report": report, "debug_path": debug_path},
        )

    except Exception as e:
        # Show a friendly error page instead of a raw 500.
        return TEMPLATES.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": repr(e),
                "engine_path": engine_path,
                "hint": "常見原因：Stockfish 路徑錯誤 / PGN 內容格式異常 / 檔案不是 UTF-8。",
            },
            status_code=500,
        )
