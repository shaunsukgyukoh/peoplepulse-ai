from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.parse import quote

import psycopg
from psycopg import sql


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def connection_params() -> dict[str, object]:
    return {
        "host": env("POSTGRES_HOST", "postgres"),
        "port": int(env("POSTGRES_PORT", "5432")),
        "dbname": env("POSTGRES_DB", "peoplepulse"),
        "user": env("POSTGRES_USER", "peoplepulse"),
        "password": env("POSTGRES_PASSWORD", "change-me-local-only"),
    }


def ensure_database() -> None:
    target_db = env("MLFLOW_POSTGRES_DB", "peoplepulse_mlflow")
    params = connection_params()
    last_error: Exception | None = None

    for attempt in range(1, 31):
        try:
            with psycopg.connect(**params, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target_db,))
                    if cur.fetchone() is None:
                        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
                        print(
                            f"[MLflow bootstrap] created database={target_db}",
                            flush=True,
                        )
                    else:
                        print(
                            f"[MLflow bootstrap] database={target_db} already exists",
                            flush=True,
                        )
            return
        except Exception as exc:  # pragma: no cover - startup retry path
            last_error = exc
            print(
                f"[MLflow bootstrap] PostgreSQL attempt={attempt}/30 failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            time.sleep(2)

    raise RuntimeError(f"Could not bootstrap MLflow database: {last_error}")


def backend_uri() -> str:
    user = quote(env("POSTGRES_USER", "peoplepulse"), safe="")
    password = quote(env("POSTGRES_PASSWORD", "change-me-local-only"), safe="")
    host = env("POSTGRES_HOST", "postgres")
    port = env("POSTGRES_PORT", "5432")
    db = quote(env("MLFLOW_POSTGRES_DB", "peoplepulse_mlflow"), safe="")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def migrate_database(uri: str) -> None:
    # MLflow's self-hosting guidance recommends migrating a SQL backend before
    # starting the tracking server. Doing it once in this bootstrap process also
    # avoids multiple Uvicorn workers racing during first-start schema setup.
    print("[MLflow bootstrap] applying MLflow DB migrations", flush=True)
    completed = subprocess.run(
        [sys.executable, "-m", "mlflow", "db", "upgrade", uri],
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"mlflow db upgrade failed with exit code {completed.returncode}"
        )
    print("[MLflow bootstrap] DB migrations complete", flush=True)


def main() -> None:
    ensure_database()
    uri = backend_uri()
    migrate_database(uri)

    os.makedirs("/mlflow/artifacts", exist_ok=True)
    os.makedirs("/mlflow/prometheus", exist_ok=True)

    workers = env("MLFLOW_WORKERS", "1")
    print(
        "[MLflow bootstrap] starting tracking server "
        f"workers={workers} backend=postgresql artifact_proxy=enabled",
        flush=True,
    )

    argv = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--backend-store-uri",
        uri,
        "--serve-artifacts",
        "--artifacts-destination",
        "/mlflow/artifacts",
        "--default-artifact-root",
        "mlflow-artifacts:/",
        "--host",
        "0.0.0.0",
        "--port",
        "5000",
        "--workers",
        workers,
        "--allowed-hosts",
        env(
            "MLFLOW_SERVER_ALLOWED_HOSTS",
            "localhost:*,127.0.0.1:*,mlflow:5000,peoplepulse-mlflow:5000",
        ),
        "--cors-allowed-origins",
        env(
            "MLFLOW_SERVER_CORS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:5000,http://127.0.0.1:5000",
        ),
        "--expose-prometheus",
        "/mlflow/prometheus",
    ]

    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
