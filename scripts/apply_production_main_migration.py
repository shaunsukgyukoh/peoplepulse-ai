from pathlib import Path

import psycopg

from peoplepulse.config import get_settings


def main() -> None:
    migrations = (
        Path("infra/postgres/migrations/005_step4_actual_report_set.sql"),
        Path("infra/postgres/migrations/008_production_employee_directory.sql"),
        Path("infra/postgres/migrations/009_activity_report_periods.sql"),
    )
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            for migration in migrations:
                cur.execute(migration.read_text(encoding="utf-8"))
                print(f"[OK] applied {migration.name}")
        conn.commit()
    print("[OK] production dashboard migrations applied")


if __name__ == "__main__":
    main()
