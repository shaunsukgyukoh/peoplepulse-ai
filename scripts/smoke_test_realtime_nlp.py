from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

import psycopg
from redis import Redis

from peoplepulse.config import get_settings
from peoplepulse.nlp.labels import LABELS


def main() -> None:
    settings = get_settings()
    event_id = f"smoke-{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    redis = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        decode_responses=True,
    )
    redis.xadd(
        settings.redis_stream_slack_events,
        {
            "schema_version": "step3.2-smoke",
            "source": "synthetic-smoke-test",
            "event_id": event_id,
            "team_id_hash": "0" * 32,
            "channel_id_hash": "1" * 32,
            "employee_id_hash": "2" * 32,
            "channel_type": "test",
            "event_ts": now.isoformat(),
            "message_ts": str(now.timestamp()),
            "thread_id_hash": "",
            "text_masked": "이번 주 업무량이 너무 많고 일정도 계속 바뀌어서 정말 답답합니다.",
            "text_length": "38",
            "received_at": now.isoformat(),
        },
        maxlen=settings.redis_stream_slack_maxlen,
        approximate=True,
    )
    print(f"[SENT] synthetic event_id={event_id}")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with psycopg.connect(settings.postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT model_name, model_device, inference_ms, active_labels, thresholds,
                           satisfied, neutral, frustrated, angry, dissatisfied, overloaded,
                           conflict, disengaged
                    FROM features.message_nlp_signal
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
        if row:
            scores = dict(zip(LABELS, row[5:], strict=True))
            print(
                json.dumps(
                    {
                        "event_id": event_id,
                        "model": row[0],
                        "device": row[1],
                        "inference_ms": row[2],
                        "active_labels": row[3],
                        "thresholds": row[4],
                        "scores": scores,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return
        time.sleep(0.5)
    raise SystemExit("Timed out waiting for the NLP worker. Check worker/Redis/PostgreSQL logs.")


if __name__ == "__main__":
    main()
