from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import psycopg

from peoplepulse.config import Settings
from peoplepulse.features.rollups import (
    build_department_slack_features,
    build_synthetic_employee_slack_features,
    month_window_end,
    slack_feature_columns,
)

ACTIVITY_FEATURE_COLUMNS = [
    "job_site_events",
    "job_site_seconds",
    "job_site_active_days",
    "web_search_events",
    "web_search_active_days",
    "document_usage_events",
    "document_active_days",
    "document_create_events",
    "document_modify_events",
    "document_view_events",
    "after_hours_search_ratio",
    "after_hours_document_ratio",
    "weekend_search_ratio",
    "weekend_document_ratio",
]


@dataclass(frozen=True)
class FeatureBuildResult:
    mode: str
    report_month: str
    slack_rows: int
    fused_rows: int


def _read_sql(settings: Settings, sql: str, params: tuple[object, ...] = ()) -> pd.DataFrame:
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            columns = [column.name for column in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def _message_frame(settings: Settings, report_month: date) -> pd.DataFrame:
    end = month_window_end(report_month)
    start = end - timedelta(days=90) + timedelta(microseconds=1)
    labels = [
        "satisfied", "neutral", "frustrated", "angry", "dissatisfied", "overloaded",
        "conflict", "disengaged",
    ]
    columns = ", ".join(["employee_id_hash", "message_ts", *labels])
    return _read_sql(
        settings,
        f"""
        SELECT {columns}
        FROM features.message_nlp_signal
        WHERE message_ts >= %s AND message_ts <= %s
        """,
        (start, end),
    )


def _replace_rows(
    settings: Settings,
    *,
    table: str,
    report_month: date,
    frame: pd.DataFrame,
    key_columns: list[str],
) -> None:
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE report_month=%s", (report_month,))
            if not frame.empty:
                columns = list(frame.columns)
                placeholders = ",".join(["%s"] * len(columns))
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                for row in frame.itertuples(index=False, name=None):
                    cur.execute(sql, tuple(row))
        conn.commit()


def _ensure_float_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result:
            result[column] = 0.0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result


def build_step5_features(
    settings: Settings,
    *,
    report_month: date,
    mode: str,
) -> FeatureBuildResult:
    if mode not in {"aggregate", "synthetic_demo"}:
        raise ValueError("mode must be aggregate or synthetic_demo")
    if mode == "synthetic_demo" and settings.app_env == "production":
        raise RuntimeError("synthetic_demo feature building is blocked in production")

    messages = _message_frame(settings, report_month)
    slack_columns = slack_feature_columns()

    if mode == "aggregate":
        mapping = _read_sql(
            settings,
            "SELECT slack_employee_id_hash, department_id_hash FROM core.slack_department_map",
        )
        slack = build_department_slack_features(
            messages,
            department_map=mapping,
            report_month=report_month,
            min_cohort_size=settings.activity_min_cohort_size,
        )
        if not slack.empty:
            slack = _ensure_float_columns(slack, slack_columns)
        _replace_rows(
            settings,
            table="features.department_monthly_slack_signal",
            report_month=report_month,
            frame=slack,
            key_columns=["department_id_hash", "report_month"],
        )

        activity = _read_sql(
            settings,
            """
            SELECT department_id_hash, report_month, cohort_employee_count,
                   job_site_events, job_site_seconds, job_site_active_days,
                   web_search_events, web_search_active_days,
                   document_usage_events, document_active_days,
                   document_create_events, document_modify_events, document_view_events,
                   after_hours_search_ratio, after_hours_document_ratio,
                   weekend_search_ratio, weekend_document_ratio
            FROM features.department_monthly_activity
            WHERE report_month=%s
            """,
            (report_month,),
        )
        if slack.empty or activity.empty:
            fused = pd.DataFrame()
        else:
            fused = activity.merge(slack, on=["department_id_hash", "report_month"], how="inner")
            fused["has_activity_data"] = True
            fused["has_slack_data"] = True
        _replace_rows(
            settings,
            table="features.department_monthly_fusion",
            report_month=report_month,
            frame=fused,
            key_columns=["department_id_hash", "report_month"],
        )
    else:
        mapping = _read_sql(
            settings,
            """
            SELECT canonical_employee_id_hash, slack_employee_id_hash,
                   activity_employee_id_hash, department_id_hash
            FROM core.synthetic_identity_map
            """,
        )
        slack = build_synthetic_employee_slack_features(
            messages,
            identity_map=mapping,
            report_month=report_month,
        )
        if not slack.empty:
            slack = _ensure_float_columns(slack, slack_columns)
        _replace_rows(
            settings,
            table="features.synthetic_employee_monthly_slack_signal",
            report_month=report_month,
            frame=slack,
            key_columns=["canonical_employee_id_hash", "report_month"],
        )

        activity = _read_sql(
            settings,
            """
            SELECT a.employee_id_hash AS activity_employee_id_hash,
                   a.department_id_hash, a.report_month,
                   a.job_site_events, a.job_site_seconds, a.job_site_active_days,
                   a.web_search_events, a.web_search_active_days,
                   a.document_usage_events, a.document_active_days,
                   a.document_create_events, a.document_modify_events, a.document_view_events,
                   a.after_hours_search_ratio, a.after_hours_document_ratio,
                   a.weekend_search_ratio, a.weekend_document_ratio,
                   i.canonical_employee_id_hash
            FROM features.synthetic_employee_monthly_activity a
            JOIN core.synthetic_identity_map i
              ON i.activity_employee_id_hash = a.employee_id_hash
            WHERE a.report_month=%s
            """,
            (report_month,),
        )
        if slack.empty or activity.empty:
            fused = pd.DataFrame()
        else:
            fused = activity.merge(
                slack.drop(columns=["department_id_hash"]),
                on=["canonical_employee_id_hash", "report_month"],
                how="inner",
            )
            fused = fused.drop(columns=["activity_employee_id_hash"])
            fused["has_activity_data"] = True
            fused["has_slack_data"] = True
        _replace_rows(
            settings,
            table="features.synthetic_employee_retention_feature",
            report_month=report_month,
            frame=fused,
            key_columns=["canonical_employee_id_hash", "report_month"],
        )

    return FeatureBuildResult(
        mode=mode,
        report_month=report_month.isoformat()[:7],
        slack_rows=len(slack),
        fused_rows=len(fused),
    )
