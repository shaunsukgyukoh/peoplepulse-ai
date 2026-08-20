from collections.abc import Mapping

from redis import Redis

from peoplepulse.config import Settings


class SlackEventPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=5,
            health_check_interval=30,
        )

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def publish_once(self, event_id: str, fields: Mapping[str, str | int]) -> str | None:
        """Publish one event using an expiring event-id deduplication key.

        Returns the Redis stream ID or None when Slack retried an event already seen.
        """
        dedup_key = f"peoplepulse:dedup:slack:{event_id}"
        inserted = self.redis.set(
            dedup_key,
            "1",
            ex=self.settings.slack_event_dedup_ttl_seconds,
            nx=True,
        )
        if not inserted:
            return None

        try:
            return self.redis.xadd(
                self.settings.redis_stream_slack_events,
                fields,
                maxlen=self.settings.redis_stream_slack_maxlen,
                approximate=True,
            )
        except Exception:
            # Allow a genuine retry if enqueueing failed after acquiring the dedup key.
            self.redis.delete(dedup_key)
            raise
