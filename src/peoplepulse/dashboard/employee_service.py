from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from peoplepulse.config import Settings
from peoplepulse.dashboard.service import SIGNALS, WORK_STRAIN_SIGNALS

TREND_WINDOWS: dict[str, tuple[str, str, str]] = {
    "hour": ("hour", "24 hours", "last_24_hours"),
    "day": ("day", "30 days", "last_30_days"),
    "week": ("week", "12 weeks", "last_12_weeks"),
    "month": ("month", "12 months", "last_12_months"),
}
TREND_TIMEZONE = "Asia/Seoul"
TIMELINE_GROUP_EXPRESSIONS: dict[str, str] = {
    "overall": "'전체'",
    "department": "COALESCE(NULLIF(BTRIM(d.department), ''), '부서 미지정')",
    "job_title": "COALESCE(NULLIF(BTRIM(d.job_title), ''), '직책 미지정')",
}


def _trend_window(granularity: str) -> tuple[str, str, str]:
    try:
        return TREND_WINDOWS[granularity]
    except KeyError as exc:
        raise ValueError(f"unsupported trend granularity: {granularity}") from exc


def _timeline_group_expression(group_by: str) -> str:
    try:
        return TIMELINE_GROUP_EXPRESSIONS[group_by]
    except KeyError as exc:
        raise ValueError(f"unsupported timeline grouping: {group_by}") from exc


@dataclass
class EmployeeDashboardService:
    settings: Settings

    def _connect(self):
        return psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row)

    @staticmethod
    def _table_exists(connection: psycopg.Connection, table_name: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (table_name,))
            row = cursor.fetchone()
        return bool(row and row["exists"])

    def list_employees(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if not self._table_exists(connection, "core.employee_directory"):
                return []
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        d.employee_id_hash,
                        d.employee_name,
                        d.department,
                        d.job_title,
                        d.is_key_staff,
                        d.is_active,
                        d.self_report_status,
                        d.self_report_updated_at,
                        s.last_activity_at,
                        s.message_count_7d
                    FROM core.employee_directory d
                    LEFT JOIN LATERAL (
                        SELECT
                            MAX(COALESCE(m.message_ts, m.received_at)) AS last_activity_at,
                            COUNT(*) FILTER (
                                WHERE COALESCE(m.message_ts, m.received_at)
                                      >= NOW() - INTERVAL '7 days'
                            )::bigint AS message_count_7d
                        FROM features.message_nlp_signal m
                        WHERE m.employee_id_hash = d.employee_id_hash
                    ) s ON TRUE
                    WHERE d.is_active = TRUE
                    ORDER BY d.is_key_staff DESC, d.department, d.employee_name
                    """
                )
                rows = cursor.fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "employee_id_hash": row["employee_id_hash"],
                    "employee_name": row["employee_name"],
                    "department": row["department"],
                    "job_title": row["job_title"],
                    "is_key_staff": bool(row["is_key_staff"]),
                    "self_report_status": row["self_report_status"],
                    "self_report_updated_at": row["self_report_updated_at"].isoformat()
                    if row["self_report_updated_at"]
                    else None,
                    "last_activity_at": row["last_activity_at"].isoformat()
                    if row["last_activity_at"]
                    else None,
                    "message_count_7d": int(row["message_count_7d"] or 0),
                }
            )
        return result

    def workforce_summary(self) -> dict[str, Any]:
        rows = self.list_employees()
        by_status = {
            "good": 0,
            "okay": 0,
            "needs_support": 0,
            "prefer_not_to_say": 0,
            "not_reported": 0,
        }
        departments: dict[str, int] = {}
        starred = 0
        for row in rows:
            status = row.get("self_report_status") or "not_reported"
            by_status[status] = by_status.get(status, 0) + 1
            departments[row["department"]] = departments.get(row["department"], 0) + 1
            if row["is_key_staff"]:
                starred += 1
        return {
            "employee_count": len(rows),
            "key_staff_count": starred,
            "departments": departments,
            "self_report": by_status,
        }

    def self_report_trend(self, employee_id_hash: str, granularity: str) -> dict[str, Any]:
        bucket_unit, interval_value, window = _trend_window(granularity)
        with self._connect() as connection:
            if not self._table_exists(connection, "core.employee_directory"):
                raise LookupError("employee directory is not initialized")
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT employee_id_hash, employee_name, department,
                           self_report_status, self_report_updated_at
                    FROM core.employee_directory
                    WHERE employee_id_hash = %s AND is_active = TRUE
                    """,
                    (employee_id_hash,),
                )
                employee = cursor.fetchone()
                if not employee:
                    raise LookupError("employee not found")

                rows: list[dict[str, Any]] = []
                if self._table_exists(connection, "core.employee_self_report_history"):
                    cursor.execute(
                        f"""
                        WITH bucketed AS (
                            SELECT
                                DATE_TRUNC(
                                    '{bucket_unit}',
                                    recorded_at AT TIME ZONE '{TREND_TIMEZONE}'
                                ) AT TIME ZONE '{TREND_TIMEZONE}' AS bucket,
                                status,
                                recorded_at
                            FROM core.employee_self_report_history
                            WHERE employee_id_hash = %s
                              AND recorded_at >= NOW() - INTERVAL '{interval_value}'
                        )
                        SELECT DISTINCT ON (bucket) bucket, status, recorded_at
                        FROM bucketed
                        ORDER BY bucket, recorded_at DESC
                        """,
                        (employee_id_hash,),
                    )
                    rows = cursor.fetchall()
                elif employee["self_report_status"] and employee["self_report_updated_at"]:
                    rows = [
                        {
                            "bucket": employee["self_report_updated_at"],
                            "status": employee["self_report_status"],
                            "recorded_at": employee["self_report_updated_at"],
                        }
                    ]

        return {
            "granularity": granularity,
            "window": window,
            "timezone": TREND_TIMEZONE,
            "source": "voluntary_self_report_only",
            "employee": {
                "employee_id_hash": employee["employee_id_hash"],
                "employee_name": employee["employee_name"],
                "department": employee["department"],
            },
            "points": [
                {
                    "bucket": row["bucket"].isoformat(),
                    "status": row["status"],
                    "recorded_at": row["recorded_at"].isoformat(),
                }
                for row in rows
            ],
        }

    def organization_support_timeline(self, granularity: str) -> dict[str, Any]:
        bucket_unit, interval_value, window = _trend_window(granularity)
        minimum_cohort_size = self.settings.activity_min_cohort_size
        scopes: dict[str, dict[str, Any]] = {}

        with self._connect() as connection:
            directory_exists = self._table_exists(connection, "core.employee_directory")
            work_signals_exist = self._table_exists(connection, "features.message_nlp_signal")
            self_reports_exist = self._table_exists(
                connection, "core.employee_self_report_history"
            )

            for group_by in TIMELINE_GROUP_EXPRESSIONS:
                group_expression = _timeline_group_expression(group_by)
                group_rows: list[dict[str, Any]] = []
                work_signal_rows: list[dict[str, Any]] = []
                self_report_rows: list[dict[str, Any]] = []

                if directory_exists:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"""
                            SELECT
                                {group_expression} AS group_name,
                                COUNT(*)::bigint AS active_employee_count
                            FROM core.employee_directory d
                            WHERE d.is_active = TRUE
                            GROUP BY 1
                            HAVING COUNT(*) >= %s
                            ORDER BY active_employee_count DESC, group_name
                            """,
                            (minimum_cohort_size,),
                        )
                        group_rows = cursor.fetchall()

                        if work_signals_exist and group_by == "department":
                            employee_signal_select = ",\n".join(
                                f"AVG(m.{signal})::double precision AS {signal}"
                                for signal in SIGNALS
                            )
                            group_signal_select = ",\n".join(
                                f"AVG({signal})::double precision AS {signal}"
                                for signal in SIGNALS
                            )
                            strain_expr = " + ".join(WORK_STRAIN_SIGNALS)
                            cursor.execute(
                                f"""
                                WITH employee_bucket AS (
                                    SELECT
                                        {group_expression} AS group_name,
                                        m.employee_id_hash,
                                        DATE_TRUNC(
                                            '{bucket_unit}',
                                            COALESCE(m.message_ts, m.received_at)
                                                AT TIME ZONE '{TREND_TIMEZONE}'
                                        ) AT TIME ZONE '{TREND_TIMEZONE}' AS bucket,
                                        COUNT(*)::bigint AS message_count,
                                        AVG(({strain_expr}) / {len(WORK_STRAIN_SIGNALS)}.0)
                                            ::double precision AS work_strain,
                                        {employee_signal_select}
                                    FROM features.message_nlp_signal m
                                    JOIN core.employee_directory d
                                      ON d.employee_id_hash = m.employee_id_hash
                                     AND d.is_active = TRUE
                                    WHERE COALESCE(m.message_ts, m.received_at)
                                              >= NOW() - INTERVAL '{interval_value}'
                                    GROUP BY group_name, m.employee_id_hash, bucket
                                )
                                SELECT
                                    group_name,
                                    bucket,
                                    COUNT(*)::bigint AS cohort_employee_count,
                                    SUM(message_count)::bigint AS message_count,
                                    AVG(work_strain)::double precision AS work_strain,
                                    {group_signal_select}
                                FROM employee_bucket
                                GROUP BY group_name, bucket
                                HAVING COUNT(*) >= %s
                                ORDER BY bucket, group_name
                                """,
                                (minimum_cohort_size,),
                            )
                            work_signal_rows = cursor.fetchall()

                        if self_reports_exist:
                            cursor.execute(
                                f"""
                                WITH ranked_report AS (
                                    SELECT
                                        {group_expression} AS group_name,
                                        h.employee_id_hash,
                                        DATE_TRUNC(
                                            '{bucket_unit}',
                                            h.recorded_at AT TIME ZONE '{TREND_TIMEZONE}'
                                        ) AT TIME ZONE '{TREND_TIMEZONE}' AS bucket,
                                        h.status,
                                        ROW_NUMBER() OVER (
                                            PARTITION BY
                                                {group_expression},
                                                h.employee_id_hash,
                                                DATE_TRUNC(
                                                    '{bucket_unit}',
                                                    h.recorded_at
                                                        AT TIME ZONE '{TREND_TIMEZONE}'
                                                )
                                            ORDER BY h.recorded_at DESC
                                        ) AS recency
                                    FROM core.employee_self_report_history h
                                    JOIN core.employee_directory d
                                      ON d.employee_id_hash = h.employee_id_hash
                                     AND d.is_active = TRUE
                                    WHERE h.recorded_at >= NOW() - INTERVAL '{interval_value}'
                                )
                                SELECT
                                    group_name,
                                    bucket,
                                    COUNT(*)::bigint AS reporting_employee_count,
                                    COUNT(*) FILTER (WHERE status = 'good')::bigint
                                        AS good_count,
                                    COUNT(*) FILTER (WHERE status = 'okay')::bigint
                                        AS okay_count,
                                    COUNT(*) FILTER (WHERE status = 'needs_support')::bigint
                                        AS needs_support_count,
                                    COUNT(*) FILTER (WHERE status = 'prefer_not_to_say')::bigint
                                        AS prefer_not_to_say_count
                                FROM ranked_report
                                WHERE recency = 1
                                GROUP BY group_name, bucket
                                HAVING COUNT(*) >= %s
                                ORDER BY bucket, group_name
                                """,
                                (minimum_cohort_size,),
                            )
                            self_report_rows = cursor.fetchall()

                scopes[group_by] = {
                    "group_by": group_by,
                    "groups": [
                        {
                            "label": row["group_name"],
                            "active_employee_count": int(row["active_employee_count"]),
                            "eligible": int(row["active_employee_count"])
                            >= minimum_cohort_size,
                        }
                        for row in group_rows
                    ],
                    "work_signal_points": [
                        {
                            "group": row["group_name"],
                            "bucket": row["bucket"].isoformat(),
                            "cohort_employee_count": int(row["cohort_employee_count"]),
                            "message_count": int(row["message_count"]),
                            "work_strain": float(row["work_strain"] or 0.0),
                            "signals": {
                                signal: float(row[signal] or 0.0) for signal in SIGNALS
                            },
                        }
                        for row in work_signal_rows
                    ],
                    "self_report_points": [
                        {
                            "group": row["group_name"],
                            "bucket": row["bucket"].isoformat(),
                            "reporting_employee_count": int(
                                row["reporting_employee_count"]
                            ),
                            "status_rates": {
                                status: int(row[f"{status}_count"])
                                / int(row["reporting_employee_count"])
                                for status in (
                                    "good",
                                    "okay",
                                    "needs_support",
                                    "prefer_not_to_say",
                                )
                            },
                        }
                        for row in self_report_rows
                    ],
                }

        return {
            "granularity": granularity,
            "window": window,
            "timezone": TREND_TIMEZONE,
            "minimum_cohort_size": minimum_cohort_size,
            "groupings": list(TIMELINE_GROUP_EXPRESSIONS),
            "sources": {
                "self_report": "voluntary_employee_self_report_only",
                "work_signals": "aggregate_work_communication_signals_only",
            },
            "source_groupings": {
                "self_report": list(TIMELINE_GROUP_EXPRESSIONS),
                "work_signals": ["department"],
            },
            "privacy": {
                "employee_first_aggregation": True,
                "individual_identifiers_returned": False,
                "psychological_diagnosis": False,
            },
            "scopes": scopes,
        }

    def department_work_signal_trend(
        self,
        *,
        granularity: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        bucket_unit, interval_value, window = _trend_window(granularity)
        minimum_cohort_size = self.settings.activity_min_cohort_size
        with self._connect() as connection:
            if not self._table_exists(connection, "core.employee_directory"):
                return {
                    "granularity": granularity,
                    "window": window,
                    "timezone": TREND_TIMEZONE,
                    "minimum_cohort_size": minimum_cohort_size,
                    "departments": [],
                    "points": [],
                }

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT department, COUNT(*)::bigint AS active_employee_count
                    FROM core.employee_directory
                    WHERE is_active = TRUE
                      AND (%s::text IS NULL OR department = %s)
                    GROUP BY department
                    ORDER BY department
                    """,
                    (department, department),
                )
                department_rows = cursor.fetchall()

                if not self._table_exists(connection, "features.message_nlp_signal"):
                    signal_rows: list[dict[str, Any]] = []
                else:
                    employee_signal_select = ",\n".join(
                        f"AVG(m.{signal})::double precision AS {signal}" for signal in SIGNALS
                    )
                    department_signal_select = ",\n".join(
                        f"AVG({signal})::double precision AS {signal}" for signal in SIGNALS
                    )
                    strain_expr = " + ".join(WORK_STRAIN_SIGNALS)
                    cursor.execute(
                        f"""
                        WITH employee_bucket AS (
                            SELECT
                                d.department,
                                m.employee_id_hash,
                                DATE_TRUNC(
                                    '{bucket_unit}',
                                    COALESCE(m.message_ts, m.received_at)
                                        AT TIME ZONE '{TREND_TIMEZONE}'
                                ) AT TIME ZONE '{TREND_TIMEZONE}' AS bucket,
                                COUNT(*)::bigint AS message_count,
                                AVG(({strain_expr}) / {len(WORK_STRAIN_SIGNALS)}.0)
                                    ::double precision AS work_strain,
                                {employee_signal_select}
                            FROM features.message_nlp_signal m
                            JOIN core.employee_directory d
                              ON d.employee_id_hash = m.employee_id_hash
                             AND d.is_active = TRUE
                            WHERE COALESCE(m.message_ts, m.received_at)
                                      >= NOW() - INTERVAL '{interval_value}'
                              AND (%s::text IS NULL OR d.department = %s)
                            GROUP BY d.department, m.employee_id_hash, bucket
                        )
                        SELECT
                            department,
                            bucket,
                            COUNT(*)::bigint AS cohort_employee_count,
                            SUM(message_count)::bigint AS message_count,
                            AVG(work_strain)::double precision AS work_strain,
                            {department_signal_select}
                        FROM employee_bucket
                        GROUP BY department, bucket
                        HAVING COUNT(*) >= %s
                        ORDER BY bucket, department
                        """,
                        (department, department, minimum_cohort_size),
                    )
                    signal_rows = cursor.fetchall()

        return {
            "granularity": granularity,
            "window": window,
            "timezone": TREND_TIMEZONE,
            "minimum_cohort_size": minimum_cohort_size,
            "aggregation": "employee_first_then_department_average",
            "source": "aggregate_work_communication_signals_only",
            "departments": [
                {
                    "department": row["department"],
                    "active_employee_count": int(row["active_employee_count"]),
                    "eligible": int(row["active_employee_count"]) >= minimum_cohort_size,
                }
                for row in department_rows
            ],
            "points": [
                {
                    "department": row["department"],
                    "bucket": row["bucket"].isoformat(),
                    "cohort_employee_count": int(row["cohort_employee_count"]),
                    "message_count": int(row["message_count"]),
                    "work_strain": float(row["work_strain"] or 0.0),
                    "signals": {
                        signal: float(row[signal] or 0.0) for signal in SIGNALS
                    },
                }
                for row in signal_rows
            ],
        }

    def set_key_staff(self, employee_id_hash: str, is_key_staff: bool) -> dict[str, Any]:
        with self._connect() as connection:
            if not self._table_exists(connection, "core.employee_directory"):
                raise LookupError("employee directory is not initialized")
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE core.employee_directory
                    SET is_key_staff = %s, updated_at = NOW()
                    WHERE employee_id_hash = %s
                    RETURNING employee_id_hash, employee_name, is_key_staff
                    """,
                    (is_key_staff, employee_id_hash),
                )
                row = cursor.fetchone()
            connection.commit()
        if not row:
            raise LookupError("employee not found")
        return {
            "employee_id_hash": row["employee_id_hash"],
            "employee_name": row["employee_name"],
            "is_key_staff": bool(row["is_key_staff"]),
        }
