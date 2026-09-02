# ruff: noqa: E501
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from peoplepulse.activity.features import build_features
from peoplepulse.activity.privacy import ContentPrivacyFilter
from peoplepulse.activity.processor import (
    ActivityUploadError,
    AnalysisPeriod,
    MonthlyActivityReportSetProcessor,
    PreparedReport,
    ReportUpload,
)
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


def _prepared_reports(
    reports: dict[ReportType, pd.DataFrame],
    *,
    period_start: date,
    period_end: date,
) -> list[PreparedReport]:
    return [
        PreparedReport(
            report_type=report_type,
            filename=f"Synthetic_{report_type.value}.xlsx",
            file_hash=report_type.value.ljust(64, "0"),
            input_rows=len(frame),
            duplicate_rows_removed=0,
            privacy_excluded_rows=0,
            frame=frame,
            period_start=period_start,
            period_end=period_end,
            period_declared=True,
        )
        for report_type, frame in reports.items()
    ]


def test_multi_month_period_is_split_into_monthly_feature_rows() -> None:
    reports = _reports()
    timestamp_columns = {
        ReportType.JOB_SITE_ACCESS: "access_date",
        ReportType.WEB_SEARCH: "searched_at",
        ReportType.DOCUMENT_USAGE: "occurred_at",
    }
    for report_type, frame in reports.items():
        august = frame.copy()
        timestamp_column = timestamp_columns[report_type]
        august[timestamp_column] = august[timestamp_column] + pd.DateOffset(months=1)
        reports[report_type] = pd.concat([frame, august], ignore_index=True)

    processor = MonthlyActivityReportSetProcessor(_settings(activity_privacy_mode="aggregate"))
    features = processor._build_features_for_period(
        _prepared_reports(
            reports,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 8, 31),
        ),
        AnalysisPeriod(date(2026, 7, 1), date(2026, 8, 31)),
    )

    assert features.synthetic_employees.empty
    assert len(features.departments) == 2
    assert set(features.departments["report_month"]) == {
        date(2026, 7, 1),
        date(2026, 8, 1),
    }
    assert features.departments["job_site_active_days"].max() <= 31


def test_mismatched_declared_workbook_periods_are_rejected() -> None:
    reports = _prepared_reports(
        _reports(),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
    )
    reports[0] = PreparedReport(
        **{
            **reports[0].__dict__,
            "period_start": date(2026, 6, 1),
            "period_end": date(2026, 7, 31),
        }
    )

    with pytest.raises(ActivityUploadError, match="workbook periods must match"):
        MonthlyActivityReportSetProcessor._resolve_analysis_period(reports)


def test_actual_format_workbooks_supply_their_own_period() -> None:
    root = Path("data/synthetic/activity/actual-format")
    paths = sorted(root.glob("*.xlsx"))
    processor = MonthlyActivityReportSetProcessor(_settings(activity_privacy_mode="aggregate"))

    prepared = [
        processor._prepare_one(ReportUpload(path.name, path.read_bytes()))[0]
        for path in paths
    ]

    assert len(prepared) == 3
    assert {report.report_type for report in prepared} == set(ReportType)
    assert {
        (report.period_start, report.period_end, report.period_declared)
        for report in prepared
    } == {(date(2026, 7, 1), date(2026, 7, 31), True)}
