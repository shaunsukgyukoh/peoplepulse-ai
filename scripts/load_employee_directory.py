from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from peoplepulse.config import get_settings
from peoplepulse.security.identifiers import pseudonymize

ALLOWED_SELF_REPORT = {"", "good", "okay", "needs_support", "prefer_not_to_say"}


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "starred", "key"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the production employee directory from CSV.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    csv_path = args.path.resolve()
    if not csv_path.exists():
        raise SystemExit(f"Employee directory CSV not found: {csv_path}")

    settings = get_settings()
    rows: list[tuple[str, str, str, str | None, bool, bool, str | None, datetime | None]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"slack_user_id", "employee_name", "department"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Missing required columns: {', '.join(sorted(missing))}")

        for index, row in enumerate(reader, start=2):
            slack_user_id = (row.get("slack_user_id") or "").strip()
            employee_name = (row.get("employee_name") or "").strip()
            department = (row.get("department") or "").strip()
            job_title = (row.get("job_title") or "").strip() or None
            self_report_status = (row.get("self_report_status") or "").strip()
            if not slack_user_id or not employee_name or not department:
                raise SystemExit(f"Row {index}: slack_user_id, employee_name and department are required")
            if self_report_status not in ALLOWED_SELF_REPORT:
                raise SystemExit(f"Row {index}: unsupported self_report_status={self_report_status!r}")

            employee_id_hash = pseudonymize(slack_user_id, settings.employee_hash_key, namespace="employee")
            self_report_value = self_report_status or None
            rows.append(
                (
                    employee_id_hash,
                    employee_name,
                    department,
                    job_title,
                    _to_bool(row.get("is_key_staff") or ""),
                    not (row.get("is_active") or "").strip().lower() in {"0", "false", "no", "n"},
                    self_report_value,
                    datetime.now(timezone.utc) if self_report_value is not None else None,
                )
            )

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO core.employee_directory (
                    employee_id_hash, employee_name, department, job_title,
                    is_key_staff, is_active, self_report_status, self_report_updated_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (employee_id_hash) DO UPDATE SET
                    employee_name = EXCLUDED.employee_name,
                    department = EXCLUDED.department,
                    job_title = EXCLUDED.job_title,
                    is_key_staff = EXCLUDED.is_key_staff,
                    is_active = EXCLUDED.is_active,
                    self_report_status = EXCLUDED.self_report_status,
                    self_report_updated_at = CASE
                        WHEN core.employee_directory.self_report_status IS DISTINCT FROM EXCLUDED.self_report_status
                        THEN EXCLUDED.self_report_updated_at
                        ELSE core.employee_directory.self_report_updated_at
                    END,
                    updated_at = NOW()
                """,
                rows,
            )
        conn.commit()

    print(f"[OK] loaded {len(rows)} employee directory rows from {csv_path}")
    print("Required CSV columns: slack_user_id,employee_name,department")
    print("Optional columns: job_title,is_key_staff,is_active,self_report_status")
    print("Extra CSV columns such as email/account metadata are safely ignored by this loader.")
    print("self_report_status is voluntary only: good|okay|needs_support|prefer_not_to_say")


if __name__ == "__main__":
    main()
