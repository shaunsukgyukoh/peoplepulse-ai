from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import UTC, datetime

import psycopg
from redis import Redis
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError

from peoplepulse.config import Settings, get_settings
from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.predictors import BaselinePredictor, Predictor, TransformerPredictor

logger = logging.getLogger("peoplepulse.nlp.worker")


def _to_datetime(slack_ts: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(slack_ts), tz=UTC)
    except (TypeError, ValueError):
        return None


def build_predictor(settings: Settings) -> Predictor:
    if settings.nlp_backend == "baseline":
        return BaselinePredictor(settings.nlp_baseline_model_path, settings.nlp_threshold)
    if settings.nlp_backend == "transformer":
        return TransformerPredictor(
            settings.nlp_model_path,
            threshold=settings.nlp_threshold,
            device=settings.nlp_device,
        )
    raise RuntimeError(f"Unsupported NLP_BACKEND={settings.nlp_backend!r}")


class NlpWorker:
    def __init__(self, settings: Settings, predictor: Predictor) -> None:
        self.settings = settings
        self.predictor = predictor
        self.consumer = os.getenv("NLP_CONSUMER_NAME") or f"{socket.gethostname()}-{os.getpid()}"
        self.redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=settings.nlp_redis_socket_timeout_seconds,
            health_check_interval=30,
        )
        self._ensure_group()
        self._last_recovery = 0.0

    def _ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(
                self.settings.redis_stream_slack_events,
                self.settings.nlp_consumer_group,
                id="0-0",
                mkstream=True,
            )
            logger.info("Created Redis consumer group=%s", self.settings.nlp_consumer_group)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _persist(
        self,
        event: dict[str, str],
        scores: dict[str, float],
        inference_ms: float,
        model_name: str,
        model_version: str,
        thresholds: dict[str, float],
        active_labels: tuple[str, ...],
        device: str,
    ) -> None:
        values = [scores[label] for label in LABELS]
        with psycopg.connect(self.settings.postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO features.message_nlp_signal (
                        event_id, employee_id_hash, channel_id_hash, channel_type,
                        message_ts, received_at, model_name, model_version, threshold, inference_ms,
                        thresholds, active_labels, model_device,
                        satisfied, neutral, frustrated, angry, dissatisfied, overloaded,
                        conflict, disengaged
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event["event_id"],
                        event["employee_id_hash"],
                        event["channel_id_hash"],
                        event.get("channel_type", "unknown"),
                        _to_datetime(event.get("message_ts", "")),
                        event.get("received_at") or datetime.now(UTC).isoformat(),
                        model_name,
                        model_version,
                        self.settings.nlp_threshold,
                        inference_ms,
                        json.dumps(thresholds),
                        list(active_labels),
                        device,
                        *values,
                    ),
                )
            conn.commit()

    def _publish_result(
        self,
        event: dict[str, str],
        scores: dict[str, float],
        inference_ms: float,
        model_name: str,
        active_labels: tuple[str, ...],
        thresholds: dict[str, float],
        device: str,
    ) -> None:
        fields: dict[str, str | float] = {
            "event_id": event["event_id"],
            "employee_id_hash": event["employee_id_hash"],
            "channel_id_hash": event["channel_id_hash"],
            "message_ts": event.get("message_ts", ""),
            "model_name": model_name,
            "model_device": device,
            "active_labels": ",".join(active_labels),
            "thresholds": json.dumps(thresholds, separators=(",", ":")),
            "inference_ms": round(inference_ms, 3),
        }
        fields.update({label: round(scores[label], 6) for label in LABELS})
        self.redis.xadd(
            self.settings.redis_stream_nlp_results,
            fields,
            maxlen=self.settings.redis_stream_nlp_maxlen,
            approximate=True,
        )

    def process(self, stream_id: str, event: dict[str, str]) -> None:
        text = event.get("text_masked", "").strip()
        if not text:
            self.redis.xack(
                self.settings.redis_stream_slack_events,
                self.settings.nlp_consumer_group,
                stream_id,
            )
            self.redis.xdel(self.settings.redis_stream_slack_events, stream_id)
            return

        start = time.perf_counter()
        prediction = self.predictor.predict(text)
        inference_ms = (time.perf_counter() - start) * 1000
        self._persist(
            event,
            prediction.scores,
            inference_ms,
            prediction.model_name,
            prediction.model_version,
            prediction.thresholds,
            prediction.active_labels,
            prediction.device,
        )
        self._publish_result(
            event,
            prediction.scores,
            inference_ms,
            prediction.model_name,
            prediction.active_labels,
            prediction.thresholds,
            prediction.device,
        )
        # DB + derived result stream succeeded: acknowledge and delete transient message text.
        self.redis.xack(
            self.settings.redis_stream_slack_events,
            self.settings.nlp_consumer_group,
            stream_id,
        )
        self.redis.xdel(self.settings.redis_stream_slack_events, stream_id)
        logger.info(
            "NLP event processed event_id=%s inference_ms=%.1f model=%s device=%s active=%s",
            event.get("event_id"),
            inference_ms,
            prediction.model_name,
            prediction.device,
            ",".join(prediction.active_labels),
        )


    def recover_stale_pending(self) -> None:
        now = time.monotonic()
        if now - self._last_recovery < self.settings.nlp_recovery_interval_seconds:
            return
        self._last_recovery = now
        try:
            result = self.redis.xautoclaim(
                self.settings.redis_stream_slack_events,
                self.settings.nlp_consumer_group,
                self.consumer,
                min_idle_time=self.settings.nlp_pending_min_idle_ms,
                start_id="0-0",
                count=self.settings.nlp_batch_size,
            )
        except ResponseError:
            logger.exception("Failed to recover pending Redis Stream entries")
            return
        messages = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else []
        for stream_id, event in messages:
            try:
                self.process(stream_id, event)
            except Exception:
                logger.exception("Failed recovered NLP processing stream_id=%s", stream_id)

    def run_forever(self) -> None:
        logger.info(
            "NLP worker started backend=%s group=%s consumer=%s",
            self.settings.nlp_backend,
            self.settings.nlp_consumer_group,
            self.consumer,
        )
        while True:
            self.recover_stale_pending()
            try:
                rows = self.redis.xreadgroup(
                    groupname=self.settings.nlp_consumer_group,
                    consumername=self.consumer,
                    streams={self.settings.redis_stream_slack_events: ">"},
                    count=self.settings.nlp_batch_size,
                    block=self.settings.nlp_block_ms,
                )
            except RedisTimeoutError:
                # A transient socket read timeout must not kill the long-running worker.
                # The configured socket timeout is intentionally longer than XREADGROUP BLOCK.
                logger.warning(
                    "Redis blocking read timed out; retrying stream read block_ms=%s socket_timeout_s=%s",
                    self.settings.nlp_block_ms,
                    self.settings.nlp_redis_socket_timeout_seconds,
                )
                continue
            if not rows:
                continue
            for _stream, messages in rows:
                for stream_id, event in messages:
                    try:
                        self.process(stream_id, event)
                    except Exception:
                        logger.exception("Failed NLP processing stream_id=%s", stream_id)
                        # Leave the message pending for explicit recovery rather than losing it.


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    settings.validate_nlp_runtime()
    predictor = build_predictor(settings)
    NlpWorker(settings, predictor).run_forever()


if __name__ == "__main__":
    main()
