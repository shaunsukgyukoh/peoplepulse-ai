# ruff: noqa: E501
from collections import Counter

import pandas as pd
import pytest

from peoplepulse.activity.features import build_features
from peoplepulse.activity.privacy import ContentPrivacyFilter
from peoplepulse.activity.report_types import ReportType
from peoplepulse.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(
        employee_hash_key="employee-hmac-secret-for-tests",
        activity_content_policy_path="configs/activity_content_policy.json",
        activity_min_cohort_size=2,
        **kwargs,
    )


def _reports() -> dict[ReportType, pd.DataFrame]:
    return {
        ReportType.JOB_SITE_ACCESS: pd.DataFrame(
            [
                {"employee_name": "A", "department": "R&D", "access_date": pd.Timestamp("2026-07-03"), "access_duration_seconds": 300.0},
                {"employee_name": "B", "department": "R&D", "access_date": pd.Timestamp("2026-07-04"), "access_duration_seconds": 600.0},
            ]
        ),
        ReportType.WEB_SEARCH: pd.DataFrame(
            [
                {"employee_name": "A", "department": "R&D", "searched_at": pd.Timestamp("2026-07-03 20:00")},
                {"employee_name": "B", "department": "R&D", "searched_at": pd.Timestamp("2026-07-04 10:00")},
            ]
        ),
        ReportType.DOCUMENT_USAGE: pd.DataFrame(
            [
                {"employee_name": "A", "department": "R&D", "occurred_at": pd.Timestamp("2026-07-03 21:00"), "action": "수정"},
                {"employee_name": "B", "department": "R&D", "occurred_at": pd.Timestamp("2026-07-04 11:00"), "action": "열람"},
            ]
        ),
    }


def test_aggregate_mode_builds_only_cohort_features() -> None:
    result = build_features(
        _reports(),
        report_month=pd.Timestamp("2026-07-01").date(),
        settings=_settings(activity_privacy_mode="aggregate"),
        source_filenames=["a.xls", "b.xls", "c.xls"],
    )
    assert len(result.departments) == 1
    assert result.synthetic_employees.empty
    row = result.departments.iloc[0]
    assert row["cohort_employee_count"] == 2
    assert row["job_site_seconds"] == 900.0


def test_synthetic_demo_requires_synthetic_filename_prefix() -> None:
    with pytest.raises(ValueError):
        build_features(
            _reports(),
            report_month=pd.Timestamp("2026-07-01").date(),
            settings=_settings(activity_privacy_mode="synthetic_demo"),
            source_filenames=["real1.xls", "real2.xls", "real3.xls"],
        )


def test_synthetic_demo_can_build_employee_features_for_synthetic_files() -> None:
    result = build_features(
        _reports(),
        report_month=pd.Timestamp("2026-07-01").date(),
        settings=_settings(activity_privacy_mode="synthetic_demo"),
        source_filenames=["Synthetic_a.xlsx", "Synthetic_b.xlsx", "Synthetic_c.xlsx"],
    )
    assert result.departments.empty
    assert len(result.synthetic_employees) == 2
    assert "employee_id_hash" in result.synthetic_employees.columns


def test_privacy_filter_returns_only_batch_counts_for_sensitive_content() -> None:
    privacy = ContentPrivacyFilter("configs/activity_content_policy.json")
    frame = pd.DataFrame(
        [
            {"employee_name": "A", "department": "R&D", "query_text": "파이썬 경력", "search_term": "이직", "searched_at": pd.Timestamp("2026-07-03")},
            {"employee_name": "A", "department": "R&D", "query_text": "정신건강 상담", "search_term": "검색", "searched_at": pd.Timestamp("2026-07-03")},
        ]
    )
    result = privacy.apply(ReportType.WEB_SEARCH, frame)
    assert len(result.frame) == 1
    assert result.excluded == Counter({"mental_health": 1})
