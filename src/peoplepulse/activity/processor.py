# ruff: noqa: E501
from __future__ import annotations

import hashlib
import io
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.errors import UniqueViolation

from peoplepulse.activity.features import FeatureFrames, build_features
from peoplepulse.activity.models import ActivityReportSetResult, UploadedReportSummary
from peoplepulse.activity.normalizers import (
    NormalizedReport,
    ReportNormalizationError,
    normalize_report,
)
from peoplepulse.activity.privacy import ContentPrivacyFilter
from peoplepulse.activity.report_types import ReportDetectionError, ReportType, detect_report_type
from peoplepulse.config import Settings


class ActivityUploadError(ValueError):
    pass


@dataclass(frozen=True)
class ReportUpload:
    filename: str
    content: bytes


@dataclass(frozen=True)
class PreparedReport:
    report_type: ReportType
    filename: str
    file_hash: str
    input_rows: int
    duplicate_rows_removed: int
    privacy_excluded_rows: int
    frame: pd.DataFrame
    period_start: date
    period_end: date
    period_declared: bool


@dataclass(frozen=True)
class AnalysisPeriod:
    start: date
    end: date

    @property
    def month_starts(self) -> list[date]:
        months: list[date] = []
        current = date(self.start.year, self.start.month, 1)
        final = date(self.end.year, self.end.month, 1)
        while current <= final:
            months.append(current)
            current = _next_month(current)
        return months


_TIMESTAMP_COLUMNS = {
    ReportType.JOB_SITE_ACCESS: "access_date",
    ReportType.WEB_SEARCH: "searched_at",
    ReportType.DOCUMENT_USAGE: "occurred_at",
}


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


@dataclass(frozen=True)
class ProcessedReportSet:
    result: ActivityReportSetResult
    department_features: pd.DataFrame
    synthetic_employee_features: pd.DataFrame


_DEPARTMENT_COLUMNS = [
    "cohort_employee_count",
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

_EMPLOYEE_COLUMNS = [column for column in _DEPARTMENT_COLUMNS if column != "cohort_employee_count"]


class MonthlyActivityReportSetProcessor:
    REQUIRED_TYPES = {
        ReportType.JOB_SITE_ACCESS,
        ReportType.WEB_SEARCH,
        ReportType.DOCUMENT_USAGE,
    }

    def __init__(self, settings: Settings) -> None:
        settings.validate_activity_runtime()
        self.settings = settings
        self.privacy_filter = ContentPrivacyFilter(settings.activity_content_policy_path)

    def _read_raw_excel(self, upload: ReportUpload) -> pd.DataFrame:
        if len(upload.content) > self.settings.activity_max_upload_bytes:
            raise ActivityUploadError(
                f"{upload.filename}: file exceeds "
                f"{self.settings.activity_max_upload_bytes // (1024 * 1024)} MB limit"
            )
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in {".xls", ".xlsx"}:
            raise ActivityUploadError("All three reports must use .xls or .xlsx")
        try:
            return pd.read_excel(
                io.BytesIO(upload.content),
                engine="calamine",
                sheet_name=0,
                header=None,
            )
        except Exception as exc:
            raise ActivityUploadError(f"Unable to read workbook: {upload.filename}") from exc

    @staticmethod
    def _event_period(
        report_type: ReportType,
        frame: pd.DataFrame,
        declared_period: tuple[date, date] | None,
    ) -> tuple[date, date]:
        timestamp_column = _TIMESTAMP_COLUMNS[report_type]
        timestamp = pd.to_datetime(frame[timestamp_column], errors="coerce")
        invalid = timestamp.isna()
        if invalid.any():
            raise ActivityUploadError(
                f"{report_type.value}: {int(invalid.sum())} rows contain invalid date/time values"
            )
        if timestamp.empty:
            raise ActivityUploadError(f"{report_type.value}: report contains no activity rows")
        event_start = timestamp.min().date()
        event_end = timestamp.max().date()
        if declared_period is None:
            return event_start, event_end
        period_start, period_end = declared_period
        event_dates = timestamp.dt.date
        match = (event_dates >= period_start) & (event_dates <= period_end)
        if not bool(match.all()):
            raise ActivityUploadError(
                f"{report_type.value}: {int((~match).sum())} rows are outside "
                f"the workbook period={period_start.isoformat()}..{period_end.isoformat()}"
            )
        return period_start, period_end

    def _prepare_one(
        self,
        upload: ReportUpload,
    ) -> tuple[PreparedReport, Counter[str]]:
        raw = self._read_raw_excel(upload)
        try:
            detected = detect_report_type(raw)
            normalized: NormalizedReport = normalize_report(raw, detected)
        except (ReportDetectionError, ReportNormalizationError) as exc:
            raise ActivityUploadError(f"{upload.filename}: {exc}") from exc

        declared_period = (
            (normalized.period_start, normalized.period_end)
            if normalized.period_start is not None and normalized.period_end is not None
            else None
        )
        period_start, period_end = self._event_period(
            normalized.report_type,
            normalized.frame,
            declared_period,
        )
        privacy = self.privacy_filter.apply(normalized.report_type, normalized.frame)
        prepared = PreparedReport(
            report_type=normalized.report_type,
            filename=upload.filename,
            file_hash=hashlib.sha256(upload.content).hexdigest(),
            input_rows=len(normalized.frame) + normalized.duplicate_rows_removed,
            duplicate_rows_removed=normalized.duplicate_rows_removed,
            privacy_excluded_rows=sum(privacy.excluded.values()),
            frame=privacy.frame,
            period_start=period_start,
            period_end=period_end,
            period_declared=declared_period is not None,
        )
        return prepared, privacy.excluded

    @staticmethod
    def _resolve_analysis_period(reports: list[PreparedReport]) -> AnalysisPeriod:
        declared = {
            (report.period_start, report.period_end)
            for report in reports
            if report.period_declared
        }
        if len(declared) > 1:
            details = ", ".join(
                f"{report.report_type.value}="
                f"{report.period_start.isoformat()}..{report.period_end.isoformat()}"
                for report in sorted(reports, key=lambda item: item.report_type.value)
            )
            raise ActivityUploadError(
                "The three workbook periods must match before they can be analyzed together "
                f"({details})"
            )
        if declared:
            period_start, period_end = next(iter(declared))
            outside = [
                report
                for report in reports
                if not report.period_declared
                and (report.period_start < period_start or report.period_end > period_end)
            ]
            if outside:
                raise ActivityUploadError(
                    "Activity dates in a workbook without period metadata fall outside the "
                    "period declared by the other workbooks"
                )
            return AnalysisPeriod(period_start, period_end)
        return AnalysisPeriod(
            min(report.period_start for report in reports),
            max(report.period_end for report in reports),
        )

    def _build_features_for_period(
        self,
        reports: list[PreparedReport],
        period: AnalysisPeriod,
    ) -> FeatureFrames:
        department_frames: list[pd.DataFrame] = []
        employee_frames: list[pd.DataFrame] = []
        suppressed_departments = 0
        for report_month in period.month_starts:
            next_month = _next_month(report_month)
            monthly_reports: dict[ReportType, pd.DataFrame] = {}
            for report in reports:
                timestamps = pd.to_datetime(
                    report.frame[_TIMESTAMP_COLUMNS[report.report_type]],
                    errors="coerce",
                )
                monthly_reports[report.report_type] = report.frame.loc[
                    (timestamps >= pd.Timestamp(report_month))
                    & (timestamps < pd.Timestamp(next_month))
                ].copy()
            if not any(not frame.empty for frame in monthly_reports.values()):
                continue
            try:
                monthly_features = build_features(
                    monthly_reports,
                    report_month=report_month,
                    settings=self.settings,
                    source_filenames=[report.filename for report in reports],
                )
            except ValueError as exc:
                raise ActivityUploadError(str(exc)) from exc
            if not monthly_features.departments.empty:
                department_frames.append(monthly_features.departments)
            if not monthly_features.synthetic_employees.empty:
                employee_frames.append(monthly_features.synthetic_employees)
            suppressed_departments += monthly_features.suppressed_departments
        return FeatureFrames(
            departments=(
                pd.concat(department_frames, ignore_index=True)
                if department_frames
                else pd.DataFrame()
            ),
            synthetic_employees=(
                pd.concat(employee_frames, ignore_index=True)
                if employee_frames
                else pd.DataFrame()
            ),
            suppressed_departments=suppressed_departments,
        )

    @staticmethod
    def _report_set_hash(reports: list[PreparedReport]) -> str:
        digest = hashlib.sha256()
        for report in sorted(reports, key=lambda item: item.report_type.value):
            digest.update(report.report_type.value.encode("utf-8"))
            digest.update(report.file_hash.encode("ascii"))
        return digest.hexdigest()

    @staticmethod
    def _ensure_complete_set(reports: list[PreparedReport]) -> None:
        report_types = [report.report_type for report in reports]
        if (
            len(report_types) != 3
            or set(report_types) != MonthlyActivityReportSetProcessor.REQUIRED_TYPES
        ):
            counts = Counter(report_types)
            missing = sorted(
                item.value
                for item in MonthlyActivityReportSetProcessor.REQUIRED_TYPES
                if counts[item] == 0
            )
            duplicate = sorted(item.value for item, count in counts.items() if count > 1)
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if duplicate:
                details.append("duplicate=" + ",".join(duplicate))
            raise ActivityUploadError("Upload exactly one of each report type (" + "; ".join(details) + ")")

    def _persist_feature_rows(
        self,
        cur: psycopg.Cursor,
        *,
        table: str,
        id_columns: list[str],
        conflict_columns: list[str],
        feature_columns: list[str],
        batch_id: str,
        frame: pd.DataFrame,
    ) -> None:
        if frame.empty:
            return
        columns = id_columns + ["report_month", "source_batch_id"] + feature_columns
        placeholders = ",".join(["%s"] * len(columns))
        conflict_target = ", ".join(conflict_columns + ["report_month"])
        update_columns = ["source_batch_id"] + [
            column for column in id_columns if column not in conflict_columns
        ] + feature_columns
        update_sql = ", ".join(f"{column}=EXCLUDED.{column}" for column in update_columns)
        update_sql += ", updated_at=NOW()"
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO UPDATE SET {update_sql}"
        )
        for row in frame.to_dict(orient="records"):
            values = [row[column] for column in id_columns]
            values.extend([row["report_month"], batch_id])
            values.extend(row[column] for column in feature_columns)
            cur.execute(sql, values)

    def _persist(
        self,
        *,
        batch_id: str,
        period: AnalysisPeriod,
        reports: list[PreparedReport],
        report_set_hash: str,
        exclusions: Counter[str],
        features: FeatureFrames,
    ) -> None:
        input_rows = sum(report.input_rows for report in reports)
        duplicates = sum(report.duplicate_rows_removed for report in reports)
        privacy_excluded = sum(report.privacy_excluded_rows for report in reports)
        report_month = period.month_starts[0]
        final_report_month = period.month_starts[-1]

        with psycopg.connect(self.settings.postgres_dsn) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE audit.activity_report_set_batch SET status='superseded' "
                        "WHERE period_start=%s AND period_end=%s "
                        "AND privacy_mode=%s AND status='completed'",
                        (period.start, period.end, self.settings.activity_privacy_mode),
                    )
                    if self.settings.activity_privacy_mode == "aggregate":
                        cur.execute(
                            "DELETE FROM features.department_monthly_activity "
                            "WHERE report_month BETWEEN %s AND %s",
                            (report_month, final_report_month),
                        )
                    else:
                        cur.execute(
                            "DELETE FROM features.synthetic_employee_monthly_activity "
                            "WHERE report_month BETWEEN %s AND %s",
                            (report_month, final_report_month),
                        )

                    cur.execute(
                        """
                        INSERT INTO audit.activity_report_set_batch (
                            batch_id, report_month, period_start, period_end,
                            privacy_mode, report_set_sha256, status,
                            policy_version, input_rows, duplicate_rows_removed,
                            privacy_excluded_rows, department_feature_rows,
                            synthetic_employee_feature_rows, suppressed_departments
                        ) VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            batch_id,
                            report_month,
                            period.start,
                            period.end,
                            self.settings.activity_privacy_mode,
                            report_set_hash,
                            self.privacy_filter.version,
                            input_rows,
                            duplicates,
                            privacy_excluded,
                            len(features.departments),
                            len(features.synthetic_employees),
                            features.suppressed_departments,
                        ),
                    )
                    for report in reports:
                        cur.execute(
                            """
                            INSERT INTO audit.activity_report_file (
                                batch_id, report_type, filename_sha256, file_sha256,
                                input_rows, duplicate_rows_removed, privacy_excluded_rows,
                                rows_after_privacy
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                batch_id,
                                report.report_type.value,
                                hashlib.sha256(Path(report.filename).name.encode("utf-8")).hexdigest(),
                                report.file_hash,
                                report.input_rows,
                                report.duplicate_rows_removed,
                                report.privacy_excluded_rows,
                                len(report.frame),
                            ),
                        )
                    for category, count in sorted(exclusions.items()):
                        cur.execute(
                            """
                            INSERT INTO audit.activity_report_exclusion_summary
                                (batch_id, category, row_count)
                            VALUES (%s,%s,%s)
                            """,
                            (batch_id, category, count),
                        )

                    if self.settings.activity_privacy_mode == "aggregate":
                        self._persist_feature_rows(
                            cur,
                            table="features.department_monthly_activity",
                            id_columns=["department_id_hash"],
                            conflict_columns=["department_id_hash"],
                            feature_columns=_DEPARTMENT_COLUMNS,
                            batch_id=batch_id,
                            frame=features.departments,
                        )
                    else:
                        self._persist_feature_rows(
                            cur,
                            table="features.synthetic_employee_monthly_activity",
                            id_columns=["employee_id_hash", "department_id_hash"],
                            conflict_columns=["employee_id_hash"],
                            feature_columns=_EMPLOYEE_COLUMNS,
                            batch_id=batch_id,
                            frame=features.synthetic_employees,
                        )
                conn.commit()
            except UniqueViolation as exc:
                conn.rollback()
                raise ActivityUploadError(
                    "This exact three-report set has already been uploaded for the period"
                ) from exc

    def process_and_persist(
        self,
        *,
        uploads: list[ReportUpload],
        report_month_value: str | None = None,
    ) -> ProcessedReportSet:
        if len(uploads) != 3:
            raise ActivityUploadError("Exactly three files must be uploaded together")
        reports: list[PreparedReport] = []
        exclusions: Counter[str] = Counter()
        for upload in uploads:
            report, excluded = self._prepare_one(upload)
            reports.append(report)
            exclusions.update(excluded)
        self._ensure_complete_set(reports)
        period = self._resolve_analysis_period(reports)
        features = self._build_features_for_period(reports, period)

        batch_id = str(uuid.uuid4())
        report_set_hash = self._report_set_hash(reports)
        self._persist(
            batch_id=batch_id,
            period=period,
            reports=reports,
            report_set_hash=report_set_hash,
            exclusions=exclusions,
            features=features,
        )

        summaries = [
            UploadedReportSummary(
                report_type=report.report_type,
                filename=Path(report.filename).name,
                input_rows=report.input_rows,
                duplicate_rows_removed=report.duplicate_rows_removed,
                privacy_excluded_rows=report.privacy_excluded_rows,
                rows_after_privacy=len(report.frame),
            )
            for report in sorted(reports, key=lambda item: item.report_type.value)
        ]
        result = ActivityReportSetResult(
            batch_id=batch_id,
            period_start=period.start,
            period_end=period.end,
            report_months=[value.strftime("%Y-%m") for value in period.month_starts],
            report_month=period.month_starts[0].strftime("%Y-%m"),
            privacy_mode=self.settings.activity_privacy_mode,
            status="completed",
            reports=summaries,
            excluded_by_category=dict(sorted(exclusions.items())),
            department_feature_rows=len(features.departments),
            synthetic_employee_feature_rows=len(features.synthetic_employees),
            suppressed_departments=features.suppressed_departments,
            created_at=datetime.now(UTC),
        )
        return ProcessedReportSet(result, features.departments, features.synthetic_employees)
