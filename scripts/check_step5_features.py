from __future__ import annotations

import argparse
from datetime import date

import psycopg

from peoplepulse.config import get_settings


def parse_month(value: str) -> date:
    year, month = value.split("-", maxsplit=1)
    return date(int(year), int(month), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--mode", choices=["aggregate", "synthetic_demo"], required=True)
    args = parser.parse_args()
    month = parse_month(args.month)
    table = (
        "features.department_monthly_fusion"
        if args.mode == "aggregate"
        else "features.synthetic_employee_retention_feature"
    )
    id_column = "department_id_hash" if args.mode == "aggregate" else "canonical_employee_id_hash"
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {id_column}, message_count_30d, work_strain_mean_30d,
                       work_strain_delta_7d_30d, job_site_events,
                       web_search_events, document_usage_events
                FROM {table}
                WHERE report_month=%s
                ORDER BY {id_column}
                """,
                (month,),
            )
            rows = cur.fetchall()
    print(f"[OK] table={table} rows={len(rows)} month={args.month}")
    for row in rows:
        masked = str(row[0])[:8] + "..."
        print(
            f"  {masked} messages30={row[1]} strain30={float(row[2]):.3f} "
            f"delta={float(row[3]):+.3f} job={row[4]} search={row[5]} docs={row[6]}"
        )


if __name__ == "__main__":
    main()
