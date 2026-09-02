# ruff: noqa: E501
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import pandas as pd
import pandera.errors

from peoplepulse.activity.report_types import DetectedReport, ReportType, normalize_header
from peoplepulse.activity.schemas import DocumentUsageSchema, JobSiteAccessSchema, WebSearchSchema


class ReportNormalizationError(ValueError):
    pass


_DURATION_RE = re.compile(
    r"^\s*(?:(?P<hours>\d+(?:\.\d+)?)\s*시간)?\s*"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)\s*분)?\s*"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)\s*초)?\s*$"
)

_PERIOD_DATE_RE = re.compile(
    r"(?<!\d)(?P<year>20\d{2})\s*(?:[-./]|년)\s*"
    r"(?P<month>\d{1,2})\s*(?:[-./]|월)\s*"
    r"(?P<day>\d{1,2})\s*일?(?!\d)"
)


def parse_korean_duration_seconds(value: object) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(float(value), 0.0)
    text = str(value).strip()
    if not text:
        return 0.0
    if text.replace(".", "", 1).isdigit():
        return max(float(text), 0.0)
    match = _DURATION_RE.match(text)
    if not match or not any(match.groupdict().values()):
        raise ReportNormalizationError("Unable to parse one or more duration values")
    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def normalize_department(value: object) -> str:
    """Normalize exported department labels to the leaf department segment."""
    text = str(value or "").strip()
    return text.split(">")[-1].strip()


@dataclass(frozen=True)
class NormalizedReport:
    report_type: ReportType
    frame: pd.DataFrame
    duplicate_rows_removed: int
    period_start: date | None = None
    period_end: date | None = None


def extract_report_period(summary_rows: pd.DataFrame) -> tuple[date, date] | None:
    """Read the export's displayed period without relying on a fixed cell."""
    texts = [
        str(value).strip()
        for value in summary_rows.to_numpy().ravel()
        if value is not None and not pd.isna(value) and str(value).strip()
    ]
    period_texts = [text for text in texts if "기간" in text]
    candidates = [*(period_texts or texts), " ".join(texts)]
    for text in candidates:
        matches = list(_PERIOD_DATE_RE.finditer(text))
        if len(matches) < 2:
            continue
        try:
            dates = [
                date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
                for match in matches[:2]
            ]
        except ValueError as exc:
            raise ReportNormalizationError("Workbook period contains an invalid date") from exc
        if dates[1] < dates[0]:
            raise ReportNormalizationError("Workbook period end is earlier than its start")
        return dates[0], dates[1]
    return None


def _extract_data(raw: pd.DataFrame, detected: DetectedReport) -> pd.DataFrame:
    header = [str(v).strip() if not pd.isna(v) else "" for v in raw.iloc[detected.header_row].tolist()]
    data = raw.iloc[detected.header_row + 1 :].copy()
    data.columns = header
    # Drop columns that are entirely empty and blank rows left by export formatting.
    data = data.loc[:, [str(c).strip() != "" for c in data.columns]]
    data = data.dropna(how="all").reset_index(drop=True)
    return data


def _column_map(columns: list[object]) -> dict[str, str]:
    return {normalize_header(column): str(column) for column in columns}


def _get(df: pd.DataFrame, mapping: dict[str, str], header: str) -> pd.Series:
    key = normalize_header(header)
    if key not in mapping:
        raise ReportNormalizationError("Workbook is missing one or more required columns")
    return df[mapping[key]]


def _validate(schema: type, frame: pd.DataFrame) -> pd.DataFrame:
    try:
        return schema.validate(frame, lazy=True)
    except pandera.errors.SchemaErrors as exc:
        count = len(exc.failure_cases) if exc.failure_cases is not None else 1
        raise ReportNormalizationError(f"Report schema validation failed ({count} failures)") from exc


def _fill_identity(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in ("employee_name", "department"):
        frame[column] = frame[column].replace(r"^\s*$", pd.NA, regex=True).ffill()
    if frame["employee_name"].isna().any() or frame["department"].isna().any():
        raise ReportNormalizationError(
            "Name/department forward-fill failed because the first detail row is blank"
        )
    frame["employee_name"] = frame["employee_name"].astype(str).str.strip()
    # The real exports are not consistent: some reports include "회사 > 부서",
    # while others contain only the final department label. Normalize to the
    # leaf segment so the same department can be joined across all three files.
    frame["department"] = frame["department"].map(normalize_department)
    return frame


def _clean_optional_text(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()
    return frame


def normalize_report(raw: pd.DataFrame, detected: DetectedReport) -> NormalizedReport:
    data = _extract_data(raw, detected)
    mapping = _column_map(list(data.columns))
    report_period = extract_report_period(detected.summary_rows)

    if detected.report_type == ReportType.JOB_SITE_ACCESS:
        frame = pd.DataFrame(
            {
                "employee_name": _get(data, mapping, "이름"),
                "department": _get(data, mapping, "부서"),
                "total_access_time_text": _get(data, mapping, "총 접속 시간"),
                "site": _get(data, mapping, "접속 사이트"),
                "title": _get(data, mapping, "타이틀"),
                "access_duration_seconds": _get(data, mapping, "접속 시간 ↓").map(
                    parse_korean_duration_seconds
                ),
                "access_date": pd.to_datetime(_get(data, mapping, "접속일"), errors="coerce"),
            }
        )
        frame = _fill_identity(frame)
        frame = _clean_optional_text(frame, ["total_access_time_text", "site", "title"])
        before = len(frame)
        frame = frame.drop_duplicates(
            subset=["employee_name", "department", "site", "title", "access_duration_seconds", "access_date"]
        ).reset_index(drop=True)
        return NormalizedReport(
            detected.report_type,
            _validate(JobSiteAccessSchema, frame),
            before - len(frame),
            *(report_period or (None, None)),
        )

    if detected.report_type == ReportType.WEB_SEARCH:
        frame = pd.DataFrame(
            {
                "employee_name": _get(data, mapping, "이름"),
                "department": _get(data, mapping, "부서"),
                "search_keyword_summary": _get(data, mapping, "검색 키워드 ↓"),
                "query_text": _get(data, mapping, "키워드"),
                "search_term": _get(data, mapping, "검색어"),
                "search_site": _get(data, mapping, "검색 사이트"),
                "searched_at": pd.to_datetime(_get(data, mapping, "검색일"), errors="coerce"),
            }
        )
        frame = _fill_identity(frame)
        frame = _clean_optional_text(
            frame, ["search_keyword_summary", "query_text", "search_term", "search_site"]
        )
        before = len(frame)
        frame = frame.drop_duplicates(
            subset=["employee_name", "department", "query_text", "search_term", "search_site", "searched_at"]
        ).reset_index(drop=True)
        return NormalizedReport(
            detected.report_type,
            _validate(WebSearchSchema, frame),
            before - len(frame),
            *(report_period or (None, None)),
        )

    if detected.report_type == ReportType.DOCUMENT_USAGE:
        frame = pd.DataFrame(
            {
                "employee_name": _get(data, mapping, "이름"),
                "department": _get(data, mapping, "부서"),
                "usage_keyword_summary": _get(data, mapping, "활용 키워드 ↓"),
                "keyword": _get(data, mapping, "키워드"),
                "document_name": _get(data, mapping, "문서명"),
                "action": _get(data, mapping, "구분"),
                "occurred_at": pd.to_datetime(_get(data, mapping, "시각"), errors="coerce"),
            }
        )
        frame = _fill_identity(frame)
        frame = _clean_optional_text(
            frame, ["usage_keyword_summary", "keyword", "document_name", "action"]
        )
        before = len(frame)
        frame = frame.drop_duplicates(
            subset=["employee_name", "department", "keyword", "document_name", "action", "occurred_at"]
        ).reset_index(drop=True)
        return NormalizedReport(
            detected.report_type,
            _validate(DocumentUsageSchema, frame),
            before - len(frame),
            *(report_period or (None, None)),
        )

    raise ReportNormalizationError("Unsupported report type")
