# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from peoplepulse.activity.report_types import ReportType
from peoplepulse.config import Settings
from peoplepulse.security.identifiers import pseudonymize


@dataclass(frozen=True)
class FeatureFrames:
    departments: pd.DataFrame
    synthetic_employees: pd.DataFrame
    suppressed_departments: int


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _after_hours(ts: pd.Timestamp, settings: Settings) -> bool:
    return bool(
        ts.hour < settings.activity_workday_start_hour
        or ts.hour >= settings.activity_workday_end_hour
    )


def _event_rows(reports: dict[ReportType, pd.DataFrame], settings: Settings) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for record in reports[ReportType.JOB_SITE_ACCESS].to_dict(orient="records"):
        ts = pd.Timestamp(record["access_date"])
        rows.append(
            {
                "employee_name": str(record["employee_name"]),
                "department": str(record["department"]),
                "report_type": ReportType.JOB_SITE_ACCESS.value,
                "timestamp": ts,
                "duration_seconds": float(record["access_duration_seconds"]),
                "after_hours": False,
                "weekend": bool(ts.dayofweek >= 5),
                "document_action": "",
            }
        )

    for record in reports[ReportType.WEB_SEARCH].to_dict(orient="records"):
        ts = pd.Timestamp(record["searched_at"])
        rows.append(
            {
                "employee_name": str(record["employee_name"]),
                "department": str(record["department"]),
                "report_type": ReportType.WEB_SEARCH.value,
                "timestamp": ts,
                "duration_seconds": 0.0,
                "after_hours": _after_hours(ts, settings),
                "weekend": bool(ts.dayofweek >= 5),
                "document_action": "",
            }
        )

    for record in reports[ReportType.DOCUMENT_USAGE].to_dict(orient="records"):
        ts = pd.Timestamp(record["occurred_at"])
        rows.append(
            {
                "employee_name": str(record["employee_name"]),
                "department": str(record["department"]),
                "report_type": ReportType.DOCUMENT_USAGE.value,
                "timestamp": ts,
                "duration_seconds": 0.0,
                "after_hours": _after_hours(ts, settings),
                "weekend": bool(ts.dayofweek >= 5),
                "document_action": str(record.get("action") or "").strip(),
            }
        )

    return pd.DataFrame(rows)


def _feature_item(group: pd.DataFrame) -> dict[str, object]:
    job = group[group["report_type"] == ReportType.JOB_SITE_ACCESS.value]
    search = group[group["report_type"] == ReportType.WEB_SEARCH.value]
    docs = group[group["report_type"] == ReportType.DOCUMENT_USAGE.value]

    search_events = len(search)
    doc_events = len(docs)
    action = docs["document_action"].str.strip().str.lower() if not docs.empty else pd.Series(dtype=str)

    return {
        "job_site_events": int(len(job)),
        "job_site_seconds": float(job["duration_seconds"].sum()) if not job.empty else 0.0,
        "job_site_active_days": int(job["timestamp"].dt.date.nunique()) if not job.empty else 0,
        "web_search_events": int(search_events),
        "web_search_active_days": int(search["timestamp"].dt.date.nunique()) if not search.empty else 0,
        "document_usage_events": int(doc_events),
        "document_active_days": int(docs["timestamp"].dt.date.nunique()) if not docs.empty else 0,
        "document_create_events": int(action.isin(["생성", "create", "created"]).sum()),
        "document_modify_events": int(action.isin(["수정", "modify", "modified", "edit", "edited"]).sum()),
        "document_view_events": int(action.isin(["열람", "view", "viewed", "read"]).sum()),
        "after_hours_search_ratio": _safe_ratio(float(search["after_hours"].sum()), float(search_events)),
        "after_hours_document_ratio": _safe_ratio(float(docs["after_hours"].sum()), float(doc_events)),
        "weekend_search_ratio": _safe_ratio(float(search["weekend"].sum()), float(search_events)),
        "weekend_document_ratio": _safe_ratio(float(docs["weekend"].sum()), float(doc_events)),
    }


def build_features(
    reports: dict[ReportType, pd.DataFrame],
    *,
    report_month: date,
    settings: Settings,
    source_filenames: list[str],
) -> FeatureFrames:
    events = _event_rows(reports, settings)
    if events.empty:
        return FeatureFrames(pd.DataFrame(), pd.DataFrame(), 0)

    department_rows: list[dict[str, object]] = []
    suppressed = 0
    if settings.activity_privacy_mode == "aggregate":
        for department, group in events.groupby("department", sort=True):
            member_count = int(group["employee_name"].nunique())
            if member_count < settings.activity_min_cohort_size:
                suppressed += 1
                continue
            item = _feature_item(group)
            item.update(
                {
                    "department_id_hash": pseudonymize(
                        str(department), settings.employee_hash_key, namespace="department"
                    ),
                    "report_month": report_month,
                    "cohort_employee_count": member_count,
                }
            )
            department_rows.append(item)

    employee_rows: list[dict[str, object]] = []
    if settings.activity_privacy_mode == "synthetic_demo":
        if not all(
            filename.startswith(settings.activity_demo_filename_prefix)
            for filename in source_filenames
        ):
            raise ValueError(
                "synthetic_demo can persist employee-level features only for files "
                "using the configured synthetic prefix"
            )
        for (employee_name, department), group in events.groupby(
            ["employee_name", "department"], sort=True
        ):
            item = _feature_item(group)
            item.update(
                {
                    "employee_id_hash": pseudonymize(
                        str(employee_name), settings.employee_hash_key, namespace="activity-report-name"
                    ),
                    "department_id_hash": pseudonymize(
                        str(department), settings.employee_hash_key, namespace="department"
                    ),
                    "report_month": report_month,
                }
            )
            employee_rows.append(item)

    return FeatureFrames(
        departments=pd.DataFrame(department_rows),
        synthetic_employees=pd.DataFrame(employee_rows),
        suppressed_departments=suppressed,
    )
