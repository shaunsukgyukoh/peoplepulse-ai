from __future__ import annotations

import argparse
import csv
from pathlib import Path

import psycopg

from peoplepulse.config import get_settings
from peoplepulse.security.identifiers import pseudonymize


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
    rows: list[tuple[str, str, str, str | None, bool, bool]] = []

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
            if not slack_user_id or not employee_name or not department:
                raise SystemExit(
                    f"Row {index}: slack_user_id, employee_name and department are required"
                )

            employee_id_hash = pseudonymize(
                slack_user_id, settings.employee_hash_key, namespace="employee"
            )
            rows.append(
                (
                    employee_id_hash,
                    employee_name,
                    department,
                    job_title,
                    _to_bool(row.get("is_key_staff") or ""),
                    (row.get("is_active") or "").strip().lower()
                    not in {"0", "false", "no", "n"},
                )
            )

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO core.employee_directory (
                    employee_id_hash, employee_name, department, job_title,
                    is_key_staff, is_active, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (employee_id_hash) DO UPDATE SET
                    employee_name = EXCLUDED.employee_name,
                    department = EXCLUDED.department,
                    job_title = EXCLUDED.job_title,
                    is_key_staff = EXCLUDED.is_key_staff,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                """,
                rows,
            )
        conn.commit()

    print(f"[OK] loaded {len(rows)} employee directory rows from {csv_path}")
    print("Required CSV columns: slack_user_id,employee_name,department")
    print("Optional columns: job_title,is_key_staff,is_active")
    print("Extra CSV columns such as email/account metadata are safely ignored by this loader.")


if __name__ == "__main__":
    main()
