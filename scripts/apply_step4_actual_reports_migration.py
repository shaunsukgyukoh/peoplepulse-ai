from pathlib import Path

import psycopg

from peoplepulse.config import get_settings

settings = get_settings()
migrations = (
    Path("infra/postgres/migrations/005_step4_actual_report_set.sql"),
    Path("infra/postgres/migrations/009_activity_report_periods.sql"),
)
with psycopg.connect(settings.postgres_dsn) as conn:
    for migration in migrations:
        conn.execute(migration.read_text(encoding="utf-8"))
        print(f"[OK] applied {migration.name}")
    conn.commit()
print("[OK] STEP 4 actual-report-set migrations applied")
