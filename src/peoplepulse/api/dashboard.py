from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent

from peoplepulse.config import get_settings
from peoplepulse.dashboard.service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _service() -> DashboardService:
    return DashboardService(get_settings())


@router.get("/overview")
def overview() -> dict:
    return _service().executive_overview()


@router.get("/slack/live")
def slack_live() -> dict:
    return _service().slack_live()


@router.get("/slack/trend")
def slack_trend(minutes: int = Query(default=60, ge=5, le=1440)) -> dict:
    return {"minutes": minutes, "points": _service().slack_trend(minutes=minutes)}


@router.get("/reports/latest")
def reports_latest() -> dict:
    return {"latest": _service().latest_report()}


@router.get("/model/attrition")
def model_attrition() -> dict:
    return _service().attrition_metrics()


@router.get("/model/nlp")
def model_nlp() -> dict:
    return {"models": _service().nlp_metrics()}


@router.get("/model/shap")
def model_shap() -> dict:
    return _service().shap_importance()


@router.get("/slack/stream", response_class=EventSourceResponse)
async def slack_stream() -> EventSourceResponse:
    settings = get_settings()

    async def events():
        last: str | None = None
        while True:
            payload = _service().slack_live()
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if encoded != last:
                last = encoded
                yield ServerSentEvent(data=encoded, event="slack_signal")
            await asyncio.sleep(settings.dashboard_stream_interval_seconds)

    return EventSourceResponse(events())
