from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from peoplepulse.config import Settings


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
                                WHERE COALESCE(m.message_ts, m.received_at) >= NOW() - INTERVAL '7 days'
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
