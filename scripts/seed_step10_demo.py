from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg

from peoplepulse.config import get_settings

MONTH = "2026-07"
ACTIVITY_FILES = [
    "data/synthetic/activity/actual-format/Synthetic_취업사이트 접속내역2026-07-01~2026-07-31.xlsx",
    "data/synthetic/activity/actual-format/Synthetic_웹 검색 내역2026-07-01~2026-07-31.xlsx",
    "data/synthetic/activity/actual-format/Synthetic_문서활용 내역2026-07-01~2026-07-31.xlsx",
]


def run(*args: str) -> None:
    print("[RUN]", " ".join(args))
    subprocess.run([sys.executable, *args], check=True, env=os.environ.copy())


def count_rows(table: str, where_sql: str = "TRUE") -> int:
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s)", (table,))
            if cursor.fetchone()[0] is None:
                return 0
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_sql}")
            return int(cursor.fetchone()[0])


def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise RuntimeError("STEP 10 synthetic demo seeding is blocked in production")
    if settings.activity_privacy_mode != "synthetic_demo":
        raise RuntimeError("Set ACTIVITY_PRIVACY_MODE=synthetic_demo for portfolio demo seeding")

    activity_count = count_rows(
        "features.synthetic_employee_monthly_activity",
        "report_month = DATE '2026-07-01'",
    )
    if activity_count == 0:
        for value in ACTIVITY_FILES:
            if not Path(value).exists():
                raise FileNotFoundError(value)
        run("scripts/upload_activity_report_set.py", "--month", MONTH, *ACTIVITY_FILES)
    else:
        print(f"[SKIP] synthetic monthly activity already exists rows={activity_count}")

    run(
        "scripts/load_identity_map.py",
        "--mode",
        "synthetic_demo",
        "--path",
        "data/synthetic/identity/canonical_employee_map.csv",
    )
    run("scripts/seed_step5_synthetic_slack.py")
    run("scripts/build_step5_features.py", "--month", MONTH, "--mode", "synthetic_demo")

    panel = Path("data/synthetic/ml/step6_attrition_panel.csv")
    if not panel.exists():
        run("scripts/generate_step6_synthetic_panel.py")
    else:
        print(f"[SKIP] STEP 6 synthetic panel already exists: {panel}")

    print("[OK] STEP 10 synthetic demo data is ready")


if __name__ == "__main__":
    main()
