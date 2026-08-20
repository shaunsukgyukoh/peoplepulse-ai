from __future__ import annotations

from pathlib import Path

import psycopg

from peoplepulse.config import get_settings


def main() -> None:
    settings = get_settings()
    sql = Path("infra/postgres/migrations/006_step5_feature_store.sql").read_text(encoding="utf-8")
    with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn:
        conn.execute(sql)
    print("[OK] STEP 5 feature-store migration applied")


if __name__ == "__main__":
    main()
