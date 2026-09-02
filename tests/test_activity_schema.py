import pandas as pd
import pytest

from peoplepulse.activity.models import ReportMonth
from peoplepulse.activity.normalizers import (
    extract_report_period,
    normalize_report,
    parse_korean_duration_seconds,
)
from peoplepulse.activity.report_types import ReportType, detect_report_type


def _job_raw() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                "기간선택 : 2026-07-01 ~ 2026-07-31\n부서선택 : (주)샘플테크",
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            ["이름", "부서", "총 접속 시간", "접속 사이트", "타이틀", "접속 시간 ↓", "접속일"],
            [
                "김가람",
                "(주)샘플테크 > 연구개발본부",
                "42분18초",
                "wanted.co.kr",
                "채용 정보",
                "5분12초",
                "2026-07-03",
            ],
            [None, None, None, "saramin.co.kr", "다른 채용", "11분03초", "2026-07-03"],
        ]
    )


def test_report_type_detected_from_headers_not_filename() -> None:
    detected = detect_report_type(_job_raw())
    assert detected.report_type == ReportType.JOB_SITE_ACCESS
    assert detected.header_row == 1


def test_forward_fill_and_department_leaf_normalization() -> None:
    detected = detect_report_type(_job_raw())
    report = normalize_report(_job_raw(), detected)
    assert report.frame["employee_name"].tolist() == ["김가람", "김가람"]
    assert report.frame["department"].tolist() == ["연구개발본부", "연구개발본부"]
    assert report.frame["access_duration_seconds"].tolist() == [312.0, 663.0]
    assert report.period_start == pd.Timestamp("2026-07-01").date()
    assert report.period_end == pd.Timestamp("2026-07-31").date()


def test_duration_parser() -> None:
    assert parse_korean_duration_seconds("1시간 2분 3초") == 3723.0
    assert parse_korean_duration_seconds("42분18초") == 2538.0


def test_report_month_parse() -> None:
    assert ReportMonth.parse("2026-07").value == "2026-07"
    with pytest.raises(ValueError):
        ReportMonth.parse("2026/07")


def test_report_period_can_span_months_and_separate_summary_cells() -> None:
    summary = pd.DataFrame([["기간선택", "2026.06.01", "2026년 8월 31일"]])

    assert extract_report_period(summary) == (
        pd.Timestamp("2026-06-01").date(),
        pd.Timestamp("2026-08-31").date(),
    )
