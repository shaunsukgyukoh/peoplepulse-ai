# ruff: noqa: E501
from __future__ import annotations

import hashlib
import io
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.errors import UniqueViolation

from peoplepulse.activity.features import FeatureFrames, build_features
from peoplepulse.activity.models import ActivityReportSetResult, ReportMonth, UploadedReportSummary
from peoplepulse.activity.normalizers import NormalizedReport, ReportNormalizationError, normalize_report
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
    def _validate_month(report_type: ReportType, frame: pd.DataFrame, report_month: ReportMonth) -> None:
        timestamp_column = {
            ReportType.JOB_SITE_ACCESS: "access_date",
            ReportType.WEB_SEARCH: "searched_at",
            ReportType.DOCUMENT_USAGE: "occurred_at",
        }[report_type]
        timestamp = pd.to_datetime(frame[timestamp_column], errors="coerce")
        invalid = timestamp.isna()
        if invalid.any():
            raise ActivityUploadError(
                f"{report_type.value}: {int(invalid.sum())} rows contain invalid date/time values"
            )
        match = (timestamp.dt.year == report_month.year) & (
            timestamp.dt.month == report_month.month
        )
        if not bool(match.all()):
            raise ActivityUploadError(
                f"{report_type.value}: {int((~match).sum())} rows are outside "
                f"report_month={report_month.value}"
            )

    def _prepare_one(
        self,
        upload: ReportUpload,
        report_month: ReportMonth,
    ) -> tuple[PreparedReport, Counter[str]]:
        raw = self._read_raw_excel(upload)
        try:
            detected = detect_report_type(raw)
            normalized: NormalizedReport = normalize_report(raw, detected)
        except (ReportDetectionError, ReportNormalizationError) as exc:
            raise ActivityUploadError(f"{upload.filename}: {exc}") from exc

        self._validate_month(normalized.report_type, normalized.frame, report_month)
        privacy = self.privacy_filter.apply(normalized.report_type, normalized.frame)
        prepared = PreparedReport(
            report_type=normalized.report_type,
            filename=upload.filename,
            file_hash=hashlib.sha256(upload.content).hexdigest(),
            input_rows=len(normalized.frame) + normalized.duplicate_rows_removed,
            duplicate_rows_removed=normalized.duplicate_rows_removed,
            privacy_excluded_rows=sum(privacy.excluded.values()),
            frame=privacy.frame,
        )
        return prepared, privacy.excluded

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
        report_month: ReportMonth,
        reports: list[PreparedReport],
        report_set_hash: str,
        exclusions: Counter[str],
        features: FeatureFrames,
    ) -> None:
        input_rows = sum(report.input_rows for report in reports)
        duplicates = sum(report.duplicate_rows_removed for report in reports)
        privacy_excluded = sum(report.privacy_excluded_rows for report in reports)

        with psycopg.connect(self.settings.postgres_dsn) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE audit.activity_report_set_batch SET status='superseded' "
                        "WHERE report_month=%s AND privacy_mode=%s AND status='completed'",
                        (report_month.first_day, self.settings.activity_privacy_mode),
                    )
                    if self.settings.activity_privacy_mode == "aggregate":
                        cur.execute(
                            "DELETE FROM features.department_monthly_activity WHERE report_month=%s",
                            (report_month.first_day,),
                        )
                    else:
                        cur.execute(
                            "DELETE FROM features.synthetic_employee_monthly_activity WHERE report_month=%s",
                            (report_month.first_day,),
                        )

                    cur.execute(
                        """
                        INSERT INTO audit.activity_report_set_batch (
                            batch_id, report_month, privacy_mode, report_set_sha256, status,
                            policy_version, input_rows, duplicate_rows_removed,
                            privacy_excluded_rows, department_feature_rows,
                            synthetic_employee_feature_rows, suppressed_departments
                        ) VALUES (%s,%s,%s,%s,'completed',%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            batch_id,
                            report_month.first_day,
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
                    "This exact three-report set has already been uploaded for the month"
                ) from exc

    def process_and_persist(
        self,
        *,
        uploads: list[ReportUpload],
        report_month_value: str,
    ) -> ProcessedReportSet:
        if len(uploads) != 3:
            raise ActivityUploadError("Exactly three files must be uploaded together")
        report_month = ReportMonth.parse(report_month_value)
        reports: list[PreparedReport] = []
        exclusions: Counter[str] = Counter()
        for upload in uploads:
            report, excluded = self._prepare_one(upload, report_month)
            reports.append(report)
            exclusions.update(excluded)
        self._ensure_complete_set(reports)

        by_type = {report.report_type: report.frame for report in reports}
        try:
            features = build_features(
                by_type,
                report_month=report_month.first_day,
                settings=self.settings,
                source_filenames=[report.filename for report in reports],
            )
        except ValueError as exc:
            raise ActivityUploadError(str(exc)) from exc

        batch_id = str(uuid.uuid4())
        report_set_hash = self._report_set_hash(reports)
        self._persist(
            batch_id=batch_id,
            report_month=report_month,
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
            report_month=report_month.value,
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
