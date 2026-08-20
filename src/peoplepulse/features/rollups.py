from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

import numpy as np
import pandas as pd

from peoplepulse.nlp.labels import LABELS

WINDOWS = (7, 30, 90)
STRAIN_LABELS = ("frustrated", "angry", "dissatisfied", "overloaded", "conflict", "disengaged")


def month_window_end(report_month: date) -> datetime:
    last_day = monthrange(report_month.year, report_month.month)[1]
    return datetime.combine(
        date(report_month.year, report_month.month, last_day),
        time.max,
        tzinfo=timezone.utc,
    )


def _window_start(anchor_end: datetime, days: int) -> datetime:
    return anchor_end - timedelta(days=days) + timedelta(microseconds=1)


def slack_feature_columns(prefix: str = "") -> list[str]:
    columns: list[str] = []
    for window in WINDOWS:
        columns.extend(
            [
                f"{prefix}message_count_{window}d",
                f"{prefix}active_days_{window}d",
                f"{prefix}message_rate_{window}d",
            ]
        )
        columns.extend(f"{prefix}{label}_mean_{window}d" for label in LABELS)
        columns.append(f"{prefix}work_strain_mean_{window}d")
    columns.extend(
        [
            f"{prefix}message_rate_delta_7d_30d",
            f"{prefix}work_strain_delta_7d_30d",
        ]
    )
    for label in LABELS:
        columns.append(f"{prefix}{label}_delta_7d_30d")
    return columns


def _safe_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.mean())


def _employee_rollup(group: pd.DataFrame, anchor_end: datetime) -> dict[str, float | int]:
    item: dict[str, float | int] = {}
    ts = pd.to_datetime(group["message_ts"], utc=True, errors="coerce")
    frame = group.assign(_ts=ts).dropna(subset=["_ts"])
    for window in WINDOWS:
        start = _window_start(anchor_end, window)
        subset = frame[(frame["_ts"] >= start) & (frame["_ts"] <= anchor_end)]
        count = int(len(subset))
        item[f"message_count_{window}d"] = count
        item[f"active_days_{window}d"] = int(subset["_ts"].dt.date.nunique()) if count else 0
        item[f"message_rate_{window}d"] = float(count / window)
        for label in LABELS:
            item[f"{label}_mean_{window}d"] = _safe_mean(subset[label])
        if count:
            strain = subset[list(STRAIN_LABELS)].mean(axis=1)
            item[f"work_strain_mean_{window}d"] = float(strain.mean())
        else:
            item[f"work_strain_mean_{window}d"] = 0.0

    item["message_rate_delta_7d_30d"] = float(
        item["message_rate_7d"] - item["message_rate_30d"]
    )
    item["work_strain_delta_7d_30d"] = float(
        item["work_strain_mean_7d"] - item["work_strain_mean_30d"]
    )
    for label in LABELS:
        item[f"{label}_delta_7d_30d"] = float(
            item[f"{label}_mean_7d"] - item[f"{label}_mean_30d"]
        )
    return item


def build_synthetic_employee_slack_features(
    messages: pd.DataFrame,
    *,
    identity_map: pd.DataFrame,
    report_month: date,
) -> pd.DataFrame:
    if messages.empty or identity_map.empty:
        return pd.DataFrame()
    merged = messages.merge(
        identity_map,
        left_on="employee_id_hash",
        right_on="slack_employee_id_hash",
        how="inner",
    )
    anchor = month_window_end(report_month)
    rows: list[dict[str, object]] = []
    for canonical_id, group in merged.groupby("canonical_employee_id_hash", sort=True):
        item: dict[str, object] = {
            "canonical_employee_id_hash": canonical_id,
            "department_id_hash": str(group["department_id_hash"].iloc[0]),
            "report_month": report_month,
        }
        item.update(_employee_rollup(group, anchor))
        rows.append(item)
    return pd.DataFrame(rows)


def build_department_slack_features(
    messages: pd.DataFrame,
    *,
    department_map: pd.DataFrame,
    report_month: date,
    min_cohort_size: int,
) -> pd.DataFrame:
    if messages.empty or department_map.empty:
        return pd.DataFrame()
    merged = messages.merge(
        department_map,
        left_on="employee_id_hash",
        right_on="slack_employee_id_hash",
        how="inner",
    )
    anchor = month_window_end(report_month)
    employee_rows: list[dict[str, object]] = []
    for (department_id, employee_id), group in merged.groupby(
        ["department_id_hash", "employee_id_hash"], sort=True
    ):
        item: dict[str, object] = {
            "department_id_hash": department_id,
            "employee_id_hash": employee_id,
        }
        item.update(_employee_rollup(group, anchor))
        employee_rows.append(item)
    employee = pd.DataFrame(employee_rows)
    if employee.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    numeric_columns = slack_feature_columns()
    for department_id, group in employee.groupby("department_id_hash", sort=True):
        cohort = int((group["message_count_90d"] > 0).sum())
        if cohort < min_cohort_size:
            continue
        item: dict[str, object] = {
            "department_id_hash": department_id,
            "report_month": report_month,
            "slack_cohort_employee_count": cohort,
        }
        # Privacy/fairness choice: employee-level metrics are averaged first so a high-volume
        # employee cannot dominate the department's linguistic-signal averages.
        for column in numeric_columns:
            if column.startswith("message_count_"):
                item[column] = int(group[column].sum())
            elif column.startswith("active_days_"):
                item[column] = float(group[column].mean())
            else:
                item[column] = float(group[column].mean())
        rows.append(item)
    return pd.DataFrame(rows)
