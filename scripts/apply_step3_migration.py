from pathlib import Path

import psycopg

from peoplepulse.config import get_settings


def main() -> None:
    settings = get_settings()
    sql = Path("infra/postgres/migrations/002_step3_nlp.sql").read_text(encoding="utf-8")
    with psycopg.connect(settings.postgres_dsn) as conn:
        conn.execute(sql)
        conn.commit()
    print("[OK] Applied STEP 3 PostgreSQL migration")


if __name__ == "__main__":
    main()
