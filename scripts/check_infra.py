"""Verify local PostgreSQL and Redis connectivity for PeoplePulse STEP 1."""

from __future__ import annotations

import sys

import psycopg
import redis

from peoplepulse.config import get_settings


def check_postgres() -> tuple[bool, str]:
    settings = get_settings()
    try:
        with psycopg.connect(settings.postgres_dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), version()")
                database, version = cur.fetchone()
                cur.execute(
                    "SELECT value FROM core.app_metadata WHERE key = 'schema_version'"
                )
                schema_version = cur.fetchone()[0]
        return True, f"database={database}, schema={schema_version}, {version.split(',')[0]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_redis() -> tuple[bool, str]:
    settings = get_settings()
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        pong = client.ping()
        info = client.info(section="server")
        return bool(pong), f"redis_version={info.get('redis_version', 'unknown')}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> int:
    checks = {
        "PostgreSQL": check_postgres(),
        "Redis": check_redis(),
    }

    failed = False
    for name, (ok, detail) in checks.items():
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        failed = failed or not ok

    if failed:
        print("\nSTEP 1 infrastructure check failed.")
        return 1

    print("\nSTEP 1 infrastructure is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
