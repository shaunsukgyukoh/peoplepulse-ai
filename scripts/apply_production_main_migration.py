from pathlib import Path

import psycopg

from peoplepulse.config import get_settings


def main() -> None:
    sql = Path("infra/postgres/migrations/008_production_employee_directory.sql").read_text(encoding="utf-8")
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("[OK] production employee directory migration applied")


if __name__ == "__main__":
    main()
