from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from peoplepulse.config import Settings
from peoplepulse.dashboard.service import SIGNALS, WORK_STRAIN_SIGNALS
from peoplepulse.dashboard.synthetic_demo import (
    empty_text_statistics,
    load_structural_text_statistics,
    load_synthetic_personas,
)

TREND_WINDOWS: dict[str, tuple[str, str, str]] = {
    "hour": ("hour", "24 hours", "last_24_hours"),
    "day": ("day", "30 days", "last_30_days"),
    "week": ("week", "12 weeks", "last_12_weeks"),
    "month": ("month", "12 months", "last_12_months"),
}
TREND_TIMEZONE = "Asia/Seoul"


def _trend_window(granularity: str) -> tuple[str, str, str]:
    try:
        return TREND_WINDOWS[granularity]
    except KeyError as exc:
        raise ValueError(f"unsupported trend granularity: {granularity}") from exc


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
                    "last_activity_at": row["last_activity_at"].isoformat()
                    if row["last_activity_at"]
                    else None,
                    "message_count_7d": int(row["message_count_7d"] or 0),
                }
            )
        return result

    def workforce_summary(self) -> dict[str, Any]:
        rows = self.list_employees()
        departments: dict[str, int] = {}
        starred = 0
        for row in rows:
            departments[row["department"]] = departments.get(row["department"], 0) + 1
            if row["is_key_staff"]:
                starred += 1
        return {
            "employee_count": len(rows),
            "key_staff_count": starred,
            "departments": departments,
        }

    def synthetic_individual_activity(self) -> dict[str, Any]:
        enabled = (
            self.settings.app_env != "production"
            and self.settings.activity_privacy_mode == "synthetic_demo"
        )
        policy = {
            "synthetic_only": True,
            "production_blocked": True,
            "real_employee_data_allowed": False,
            "raw_messages_returned": False,
            "individual_slack_nlp_visible": False,
            "sentiment_or_tone_inference": False,
            "psychological_diagnosis": False,
        }
        if not enabled:
            return {
                "enabled": False,
                "scope": "synthetic_demo_only",
                "unavailable_reason": (
                    "Set APP_ENV=development and ACTIVITY_PRIVACY_MODE=synthetic_demo "
                    "to enable the fictional-person activity demo."
                ),
                "personas": [],
                "policy": policy,
            }

        self.settings.validate_activity_runtime()
        personas = load_synthetic_personas(
            self.settings.dashboard_synthetic_identity_path,
            secret=self.settings.employee_hash_key,
        )
        structural_stats = load_structural_text_statistics(
            self.settings.dashboard_synthetic_messages_path
        )
        activity_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
        with self._connect() as connection:
            if self._table_exists(connection, "features.synthetic_employee_monthly_activity"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            a.employee_id_hash,
                            a.report_month,
                            a.web_search_events,
                            a.web_search_active_days,
                            a.document_usage_events,
                            a.document_active_days,
                            a.document_create_events,
                            a.document_modify_events,
                            a.document_view_events,
                            a.after_hours_search_ratio,
                            a.after_hours_document_ratio,
                            a.weekend_search_ratio,
                            a.weekend_document_ratio
                        FROM features.synthetic_employee_monthly_activity a
                        JOIN audit.activity_report_set_batch b
                          ON b.batch_id = a.source_batch_id
                         AND b.privacy_mode = 'synthetic_demo'
                        ORDER BY a.report_month, a.employee_id_hash
                        """
                    )
                    for row in cursor.fetchall():
                        activity_by_hash[str(row["employee_id_hash"]).strip()].append(
                            {
                                "report_month": row["report_month"].isoformat(),
                                "web_search_events": int(row["web_search_events"]),
                                "web_search_active_days": int(row["web_search_active_days"]),
                                "document_usage_events": int(row["document_usage_events"]),
                                "document_active_days": int(row["document_active_days"]),
                                "document_create_events": int(row["document_create_events"]),
                                "document_modify_events": int(row["document_modify_events"]),
                                "document_view_events": int(row["document_view_events"]),
                                "after_hours_search_ratio": float(
                                    row["after_hours_search_ratio"]
                                ),
                                "after_hours_document_ratio": float(
                                    row["after_hours_document_ratio"]
                                ),
                                "weekend_search_ratio": float(row["weekend_search_ratio"]),
                                "weekend_document_ratio": float(
                                    row["weekend_document_ratio"]
                                ),
                            }
                        )

        result_personas = []
        for persona in personas:
            activity_hash = persona["activity_employee_id_hash"]
            public_persona = {
                key: value
                for key, value in persona.items()
                if key != "activity_employee_id_hash"
            }
            result_personas.append(
                {
                    **public_persona,
                    "fictional": True,
                    "activity_points": activity_by_hash.get(activity_hash, []),
                    "text_statistics": structural_stats.get(
                        persona["canonical_employee_key"],
                        empty_text_statistics(),
                    ),
                }
            )
        return {
            "enabled": True,
            "scope": "synthetic_demo_only",
            "unavailable_reason": None,
            "personas": result_personas,
            "policy": policy,
            "sources": {
                "activity": "verified_synthetic_monthly_activity_features",
                "text": "offline_synthetic_fixture_structural_counts_only",
            },
        }

    def organization_support_timeline(self, granularity: str) -> dict[str, Any]:
        result = self.department_work_signal_trend(granularity=granularity)
        return {
            "granularity": result["granularity"],
            "window": result["window"],
            "timezone": result["timezone"],
            "minimum_cohort_size": result["minimum_cohort_size"],
            "grouping": "department",
            "aggregation": result["aggregation"],
            "source": result["source"],
            "suppressed_department_count": result["suppressed_department_count"],
            "departments": result["departments"],
            "points": result["points"],
            "privacy": {
                "individual_identifiers_returned": False,
                "raw_messages_returned": False,
                "psychological_diagnosis": False,
            },
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
                    "aggregation": "employee_first_then_department_average",
                    "source": "aggregate_work_communication_signals_only",
                    "suppressed_department_count": 0,
                    "departments": [],
                    "points": [],
                }

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) FILTER (
                        WHERE active_employee_count < %s
                    )::bigint AS suppressed_department_count
                    FROM (
                        SELECT department, COUNT(*)::bigint AS active_employee_count
                        FROM core.employee_directory
                        WHERE is_active = TRUE
                          AND (%s::text IS NULL OR department = %s)
                        GROUP BY department
                    ) department_counts
                    """,
                    (minimum_cohort_size, department, department),
                )
                department_summary = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT department, COUNT(*)::bigint AS active_employee_count
                    FROM core.employee_directory
                    WHERE is_active = TRUE
                      AND (%s::text IS NULL OR department = %s)
                    GROUP BY department
                    HAVING COUNT(*) >= %s
                    ORDER BY department
                    """,
                    (department, department, minimum_cohort_size),
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
            "suppressed_department_count": int(
                department_summary["suppressed_department_count"] or 0
            ),
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
