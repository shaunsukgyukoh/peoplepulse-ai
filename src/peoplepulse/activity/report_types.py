from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class ReportType(StrEnum):
    JOB_SITE_ACCESS = "job_site_access"
    WEB_SEARCH = "web_search"
    DOCUMENT_USAGE = "document_usage"


@dataclass(frozen=True)
class ReportDefinition:
    report_type: ReportType
    required_headers: frozenset[str]


_HEADER_CLEAN_RE = re.compile(r"[\s↓↑]+")


def normalize_header(value: object) -> str:
    text = "" if value is None else str(value)
    return _HEADER_CLEAN_RE.sub("", text.strip()).lower()


REPORT_DEFINITIONS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        ReportType.JOB_SITE_ACCESS,
        frozenset(
            normalize_header(v)
            for v in ["이름", "부서", "총 접속 시간", "접속 사이트", "타이틀", "접속 시간 ↓", "접속일"]
        ),
    ),
    ReportDefinition(
        ReportType.WEB_SEARCH,
        frozenset(
            normalize_header(v)
            for v in ["이름", "부서", "검색 키워드 ↓", "키워드", "검색어", "검색 사이트", "검색일"]
        ),
    ),
    ReportDefinition(
        ReportType.DOCUMENT_USAGE,
        frozenset(
            normalize_header(v)
            for v in ["이름", "부서", "활용 키워드 ↓", "키워드", "문서명", "구분", "시각"]
        ),
    ),
)


@dataclass(frozen=True)
class DetectedReport:
    report_type: ReportType
    header_row: int
    summary_rows: pd.DataFrame


class ReportDetectionError(ValueError):
    pass


def detect_report_type(raw: pd.DataFrame, *, scan_rows: int = 10) -> DetectedReport:
    """Detect the report from its header signature, not the filename.

    The three real exports currently place a period/department summary above the
    column header. We intentionally scan several rows so the parser survives a
    future extra title line without relying on a fixed row number.
    """
    limit = min(scan_rows, len(raw))
    matches: list[tuple[ReportType, int]] = []
    for row_idx in range(limit):
        row_headers = frozenset(
            normalize_header(v)
            for v in raw.iloc[row_idx].tolist()
            if normalize_header(v)
        )
        for definition in REPORT_DEFINITIONS:
            if definition.required_headers.issubset(row_headers):
                matches.append((definition.report_type, row_idx))

    if not matches:
        raise ReportDetectionError("Unable to identify report type from workbook headers")
    unique = {(report_type, row_idx) for report_type, row_idx in matches}
    if len(unique) != 1:
        raise ReportDetectionError("Workbook header matches more than one report type")

    report_type, header_row = unique.pop()
    return DetectedReport(report_type, header_row, raw.iloc[:header_row].copy())
