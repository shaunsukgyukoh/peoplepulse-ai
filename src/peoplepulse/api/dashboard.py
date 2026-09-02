from __future__ import annotations

import asyncio
import hmac
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from peoplepulse.config import get_settings
from peoplepulse.dashboard.employee_service import EmployeeDashboardService
from peoplepulse.dashboard.service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _service() -> DashboardService:
    return DashboardService(get_settings())


def _employee_service() -> EmployeeDashboardService:
    return EmployeeDashboardService(get_settings())


def _require_admin_token(value: str | None) -> None:
    expected = get_settings().activity_admin_token
    if not value or not expected or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")


class KeyStaffUpdate(BaseModel):
    is_key_staff: bool


TrendGranularity = Literal["hour", "day", "week", "month"]


@router.get("/overview")
def overview() -> dict:
    result = _service().executive_overview()
    # Production main keeps model details and organization-wide Slack inference
    # out of the HR UI payload. Slack signals are exposed only by the
    # department/cohort timeline endpoints below.
    result.pop("nlp_model", None)
    result.pop("attrition_model", None)
    result.pop("slack", None)
    result["workforce"] = _employee_service().workforce_summary()
    return result


@router.get("/employees")
def employees() -> dict:
    return {
        "employees": _employee_service().list_employees(),
        "summary": _employee_service().workforce_summary(),
        "signal_policy": {
            "individual_slack_nlp_visible": False,
            "key_staff_source": "manual_manager_designation_only",
            "department_minimum_cohort_size": get_settings().activity_min_cohort_size,
            "timeline_grouping": "department",
        },
    }


@router.patch("/employees/{employee_id_hash}/key-staff")
def update_key_staff(
    employee_id_hash: str,
    body: KeyStaffUpdate,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    try:
        return _employee_service().set_key_staff(employee_id_hash, body.is_key_staff)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/departments/work-signals/trend")
def department_work_signal_trend(
    granularity: Annotated[TrendGranularity, Query()] = "day",
    department: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> dict:
    return _employee_service().department_work_signal_trend(
        granularity=granularity,
        department=department,
    )


@router.get("/organization/support-timeline")
def organization_support_timeline(
    granularity: Annotated[TrendGranularity, Query()] = "day",
) -> dict:
    return _employee_service().organization_support_timeline(granularity)


@router.get("/reports/latest")
def reports_latest() -> dict:
    return {"latest": _service().latest_report()}


@router.get("/model/attrition", include_in_schema=False)
def model_attrition() -> dict:
    # Kept only for backwards compatibility with the portfolio branch/API.
    # Production dashboard does not call this endpoint.
    return _service().attrition_metrics()


@router.get("/model/nlp", include_in_schema=False)
def model_nlp() -> dict:
    return {"models": _service().nlp_metrics()}


@router.get("/model/shap", include_in_schema=False)
def model_shap() -> dict:
    return _service().shap_importance()


@router.get("/slack/stream", response_class=EventSourceResponse)
async def slack_stream():
    settings = get_settings()
    service = _service()
    last: str | None = None
    while True:
        # psycopg is synchronous, so keep database reads off the ASGI event loop.
        snapshot = await asyncio.to_thread(service.slack_live)
        # The stream is invalidation-only: clients receive no organization-wide
        # inferred scores and refetch the cohort-protected department timeline.
        payload = {"last_message_at": snapshot.get("last_message_at")}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if encoded != last:
            last = encoded
            # FastAPI 0.141+ encodes ServerSentEvent.data as JSON. Yield the
            # object itself so EventSource.message.data remains valid JSON.
            yield ServerSentEvent(data=payload, event="slack_signal")
        await asyncio.sleep(settings.dashboard_stream_interval_seconds)
