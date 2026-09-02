from datetime import date

import pandas as pd
import pytest

from peoplepulse.activity.processor import (
    ActivityUploadError,
    MonthlyActivityReportSetProcessor,
    PreparedReport,
)
from peoplepulse.activity.report_types import ReportType


def _prepared(report_type: ReportType) -> PreparedReport:
    return PreparedReport(
        report_type=report_type,
        filename=f"{report_type.value}.xls",
        file_hash="a" * 64,
        input_rows=1,
        duplicate_rows_removed=0,
        privacy_excluded_rows=0,
        frame=pd.DataFrame(),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        period_declared=True,
    )


def test_report_set_requires_one_of_each_type() -> None:
    MonthlyActivityReportSetProcessor._ensure_complete_set(
        [
            _prepared(ReportType.JOB_SITE_ACCESS),
            _prepared(ReportType.WEB_SEARCH),
            _prepared(ReportType.DOCUMENT_USAGE),
        ]
    )

    with pytest.raises(ActivityUploadError):
        MonthlyActivityReportSetProcessor._ensure_complete_set(
            [
                _prepared(ReportType.JOB_SITE_ACCESS),
                _prepared(ReportType.JOB_SITE_ACCESS),
                _prepared(ReportType.DOCUMENT_USAGE),
            ]
        )
