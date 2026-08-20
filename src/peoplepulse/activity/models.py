from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from peoplepulse.activity.report_types import ReportType

PrivacyMode = Literal["aggregate", "synthetic_demo"]


class ReportMonth(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)

    @classmethod
    def parse(cls, value: str) -> "ReportMonth":
        try:
            year_s, month_s = value.split("-", maxsplit=1)
            return cls(year=int(year_s), month=int(month_s))
        except Exception as exc:
            raise ValueError("report_month must use YYYY-MM format") from exc

    @property
    def value(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)


class UploadedReportSummary(BaseModel):
    report_type: ReportType
    filename: str
    input_rows: int
    duplicate_rows_removed: int
    privacy_excluded_rows: int
    rows_after_privacy: int


class ActivityReportSetResult(BaseModel):
    batch_id: str
    report_month: str
    privacy_mode: PrivacyMode
    status: str
    reports: list[UploadedReportSummary]
    excluded_by_category: dict[str, int]
    department_feature_rows: int
    synthetic_employee_feature_rows: int
    suppressed_departments: int
    created_at: datetime
