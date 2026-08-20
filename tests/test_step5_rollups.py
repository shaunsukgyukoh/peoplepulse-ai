from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

from peoplepulse.features.rollups import (
    build_department_slack_features,
    build_synthetic_employee_slack_features,
    month_window_end,
)
from peoplepulse.nlp.labels import LABELS


def _row(employee: str, ts: datetime, *, strain: float, satisfied: float = 0.2) -> dict[str, object]:
    row: dict[str, object] = {
        "employee_id_hash": employee,
        "message_ts": ts,
        "satisfied": satisfied,
        "neutral": 0.2,
        "frustrated": strain,
        "angry": strain,
        "dissatisfied": strain,
        "overloaded": strain,
        "conflict": strain,
        "disengaged": strain,
    }
    return row


def test_synthetic_rollup_detects_recent_strain_increase() -> None:
    month = date(2026, 7, 1)
    end = month_window_end(month)
    rows = []
    for days_ago in range(30):
        strain = 0.8 if days_ago < 7 else 0.2
        rows.append(_row("slack-a", end - timedelta(days=days_ago), strain=strain))
    messages = pd.DataFrame(rows)
    mapping = pd.DataFrame(
        [
            {
                "canonical_employee_id_hash": "canon-a",
                "slack_employee_id_hash": "slack-a",
                "activity_employee_id_hash": "activity-a",
                "department_id_hash": "dept-a",
            }
        ]
    )
    result = build_synthetic_employee_slack_features(
        messages, identity_map=mapping, report_month=month
    )
    assert len(result) == 1
    assert result.loc[0, "work_strain_delta_7d_30d"] > 0.3
    assert result.loc[0, "message_count_30d"] == 30


def test_department_signal_mean_is_employee_first_not_message_weighted() -> None:
    month = date(2026, 7, 1)
    end = month_window_end(month)
    rows = []
    # High-volume employee with high strain.
    for i in range(20):
        rows.append(_row("e1", end - timedelta(hours=i), strain=0.9))
    # Low-volume employee with low strain.
    rows.append(_row("e2", end - timedelta(hours=1), strain=0.1))
    messages = pd.DataFrame(rows)
    mapping = pd.DataFrame(
        [
            {"slack_employee_id_hash": "e1", "department_id_hash": "dept"},
            {"slack_employee_id_hash": "e2", "department_id_hash": "dept"},
        ]
    )
    result = build_department_slack_features(
        messages,
        department_map=mapping,
        report_month=month,
        min_cohort_size=2,
    )
    assert len(result) == 1
    # Employee-first average is ~0.5; raw-message weighted would be ~0.86.
    assert 0.45 <= result.loc[0, "work_strain_mean_7d"] <= 0.55
    assert result.loc[0, "message_count_7d"] == 21
