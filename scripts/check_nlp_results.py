import psycopg

from peoplepulse.config import get_settings


def main() -> None:
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*), round(avg(inference_ms)::numeric, 2)
                FROM features.message_nlp_signal
                """
            )
            count, avg_ms = cur.fetchone()
    print(f"[OK] NLP rows={count} avg_inference_ms={avg_ms}")


if __name__ == "__main__":
    main()
