from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def download_file(
    store: dict[str, dict[str, str]],
    report_id: str,
    kind: str,
    *,
    fallback_dir: str | Path | None = None,
) -> FileResponse:
    """Download report artifacts.

    MVP note:
    - The server keeps an in-memory map (store) from report_id -> file paths.
    - Artifacts are also written to disk (temp dir). After a server restart,
      the in-memory map is lost, but the files may still exist.

    This helper supports a best-effort disk fallback when store misses.
    """

    # 1) Prefer store mapping (fast path)
    path: str | None = None
    if report_id in store and kind in store[report_id]:
        path = store[report_id][kind]

    # 2) Fallback to disk if requested
    if path is None and fallback_dir is not None:
        fallback_dir = Path(fallback_dir)
        cand = fallback_dir / f"{report_id}.{kind}"
        if cand.exists():
            path = str(cand)

    if path is None:
        raise HTTPException(status_code=404, detail="report_id not found")

    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="file missing")

    media_type = "application/json" if kind == "json" else "text/html"
    filename = f"chessdna_report_{report_id}.{kind}"
    return FileResponse(path=path, media_type=media_type, filename=filename)
