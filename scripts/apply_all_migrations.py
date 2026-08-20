from __future__ import annotations

from pathlib import Path

import psycopg

from peoplepulse.config import get_settings

MIGRATIONS = [
    "002_step3_nlp.sql",
    "003_step3_runtime_thresholds.sql",
    "005_step4_actual_report_set.sql",
    "006_step5_feature_store.sql",
    "007_step6_synthetic_ml.sql",
]


def main() -> None:
    settings = get_settings()
    root = Path("infra/postgres/migrations")
    with psycopg.connect(settings.postgres_dsn, autocommit=True) as connection:
        for name in MIGRATIONS:
            sql = (root / name).read_text(encoding="utf-8")
            connection.execute(sql)
            print(f"[OK] migration {name}")
    print("[OK] all portfolio migrations applied")


if __name__ == "__main__":
    main()
