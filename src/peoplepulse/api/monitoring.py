from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from peoplepulse.config import get_settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/summary")
def monitoring_summary() -> dict:
    path = Path(get_settings().mlops_monitoring_summary_path)
    if not path.exists():
        return {"status": "not_ready", "message": "No STEP 8 monitoring snapshot has been generated yet."}
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evidently/latest")
def latest_evidently_report() -> FileResponse:
    path = Path(get_settings().mlops_monitoring_latest_html_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No Evidently report has been generated yet")
    return FileResponse(path, media_type="text/html", filename="peoplepulse-evidently-data-drift.html")
