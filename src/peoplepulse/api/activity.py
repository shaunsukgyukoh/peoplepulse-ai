# ruff: noqa: E501
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse

from peoplepulse.activity.models import ActivityReportSetResult
from peoplepulse.activity.processor import (
    ActivityUploadError,
    MonthlyActivityReportSetProcessor,
    ReportUpload,
)
from peoplepulse.config import get_settings

router = APIRouter(tags=["monthly-activity"])


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"One report exceeds {max_bytes // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/admin/activity-upload", response_class=HTMLResponse, include_in_schema=False)
def activity_upload_page() -> str:
    return """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PeoplePulse Monthly Report Set Upload</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;background:#f6f7f9;margin:0;color:#111827}.wrap{max-width:820px;margin:48px auto;padding:0 20px}
.card{background:white;border:1px solid #e5e7eb;border-radius:14px;padding:26px;box-shadow:0 8px 24px rgba(0,0,0,.05)}
h1{margin-top:0}label{display:block;margin-top:18px;font-weight:650}input,button{box-sizing:border-box;width:100%;font-size:16px;padding:11px;margin-top:7px;border:1px solid #d1d5db;border-radius:8px}
button{background:#111827;color:white;cursor:pointer;font-weight:700}.note{background:#f3f4f6;padding:14px;border-radius:8px;margin-top:20px;line-height:1.55}.warning{background:#fff7ed;border:1px solid #fed7aa;padding:14px;border-radius:8px;margin-top:16px;line-height:1.55}.result{white-space:pre-wrap;margin-top:18px;padding:14px;border-radius:8px;background:#0b1020;color:#d1fae5;display:none}.filegroup{margin-top:18px;padding:14px;border:1px solid #e5e7eb;border-radius:10px}
</style></head>
<body><div class="wrap"><div class="card"><h1>Activity Report Set</h1><p>엑셀 표시 기간 자동 인식 · 실제 3개 보고서 형식용 STEP 4 ingestion</p>
<form id="uploadForm">
<label>Admin token<input type="password" name="admin_token" autocomplete="off" required></label>
<div class="filegroup"><strong>① 취업사이트 접속내역</strong><input type="file" name="files" accept=".xls,.xlsx" required></div>
<div class="filegroup"><strong>② 웹 검색 내역</strong><input type="file" name="files" accept=".xls,.xlsx" required></div>
<div class="filegroup"><strong>③ 문서활용 내역</strong><input type="file" name="files" accept=".xls,.xlsx" required></div>
<br><button type="submit">3개 파일 검증 및 처리</button></form>
<div class="warning">파일명으로 종류나 기간을 신뢰하지 않습니다. 각 workbook의 실제 헤더에서 report type과 표시 기간을 읽고, 정확히 3종이 하나씩 있으며 세 기간이 같은지 검증합니다. 여러 달이면 월별 feature로 자동 분할합니다.</div>
<div class="note">운영 기본값은 부서/코호트 집계입니다. 이름·검색문·타이틀·문서명·사이트는 PostgreSQL에 저장하지 않으며 민감 내용은 batch-level 제외 건수만 남깁니다. 직원별 feature는 Synthetic_ 파일 + synthetic_demo 모드에서만 허용됩니다.</div>
<div class="result" id="result"></div></div></div>
<script>
const form=document.getElementById('uploadForm'),box=document.getElementById('result');
form.addEventListener('submit',async(e)=>{e.preventDefault();box.style.display='block';box.textContent='Processing 3 reports...';
 const res=await fetch('/api/v1/activity/report-sets',{method:'POST',body:new FormData(form)});const data=await res.json();
 box.textContent=JSON.stringify(data,null,2);});
</script></body></html>
"""


@router.post(
    "/api/v1/activity/report-sets",
    response_model=ActivityReportSetResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_monthly_activity_report_set(
    admin_token: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
) -> ActivityReportSetResult:
    settings = get_settings()
    settings.validate_activity_api_runtime()
    if not hmac.compare_digest(admin_token, settings.activity_admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    if len(files) != 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Exactly three activity report files are required",
        )

    uploads: list[ReportUpload] = []
    for file in files:
        content = await _read_upload_limited(file, settings.activity_max_upload_bytes)
        uploads.append(ReportUpload(filename=file.filename or "report.xls", content=content))

    processor = MonthlyActivityReportSetProcessor(settings)
    try:
        processed = processor.process_and_persist(
            uploads=uploads,
        )
    except (ActivityUploadError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return processed.result
