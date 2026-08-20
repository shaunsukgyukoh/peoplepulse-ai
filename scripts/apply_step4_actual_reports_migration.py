from pathlib import Path

import psycopg

from peoplepulse.config import get_settings

settings = get_settings()
sql = Path("infra/postgres/migrations/005_step4_actual_report_set.sql").read_text(encoding="utf-8")
with psycopg.connect(settings.postgres_dsn) as conn:
    conn.execute(sql)
    conn.commit()
print("[OK] STEP 4 actual-report-set migration applied")
