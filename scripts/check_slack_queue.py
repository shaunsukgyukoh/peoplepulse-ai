from redis import Redis

from peoplepulse.config import get_settings


SAFE_FIELDS = {
    "schema_version",
    "source",
    "event_id",
    "team_id_hash",
    "channel_id_hash",
    "employee_id_hash",
    "channel_type",
    "event_ts",
    "message_ts",
    "thread_id_hash",
    "text_length",
    "received_at",
}


def main() -> None:
    settings = get_settings()
    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        decode_responses=True,
    )
    client.ping()
    stream = settings.redis_stream_slack_events
    length = client.xlen(stream)
    print(f"[OK] Redis stream={stream} length={length}")

    if length:
        newest = client.xrevrange(stream, count=1)[0]
        stream_id, fields = newest
        safe = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
        print(f"[OK] newest_stream_id={stream_id}")
        for key in sorted(safe):
            print(f"  {key}={safe[key]}")
        print("[PRIVACY] text_masked is intentionally not printed by this check.")


if __name__ == "__main__":
    main()
