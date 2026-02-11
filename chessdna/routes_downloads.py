from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def download_file(store: dict[str, dict[str, str]], report_id: str, kind: str) -> FileResponse:
    if report_id not in store:
        raise HTTPException(status_code=404, detail="report_id not found (server restarted?)")
    if kind not in store[report_id]:
        raise HTTPException(status_code=404, detail="file kind not found")

    path = store[report_id][kind]
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="file missing")

    media_type = "application/json" if kind == "json" else "text/html"
    filename = f"chessdna_report_{report_id}.{kind}"
    return FileResponse(path=path, media_type=media_type, filename=filename)
