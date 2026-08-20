# STEP 2 — Slack Socket Mode → Redis Streams

## Goal

Receive human-authored messages from Slack public/private work channels that the app is a member of, apply minimal privacy preprocessing, pseudonymize Slack identifiers, and enqueue the event in an ephemeral Redis Stream for STEP 3 NLP processing.

## Flow

```text
Slack workspace
  -> Events API
  -> Socket Mode (outbound WebSocket, no public Request URL)
  -> Slack Bolt for Python
  -> reject bot/system/subtype events
  -> basic PII redaction
  -> HMAC pseudonymization of user/channel/team IDs
  -> Redis Stream: peoplepulse:slack-events
  -> STEP 3 NLP worker (next)
```

## Privacy decisions

- No DM or group-DM subscriptions in the portfolio MVP.
- Original Slack user/channel/team IDs are not placed in Redis.
- Common e-mail, phone, URL and Slack mention patterns are redacted before enqueueing.
- Slack message text is transient; Redis AOF/RDB persistence is disabled.
- The stream is approximately capped by `REDIS_STREAM_SLACK_MAXLEN`.
- STEP 3 will consume and delete processed message entries and persist only derived features.
- Application logs never include message text.

## Reliability decisions

- Slack `event_id` is used for retry deduplication.
- Dedup keys expire after `SLACK_EVENT_DEDUP_TTL_SECONDS`.
- If `XADD` fails after acquiring the dedup key, the key is removed so Slack retries can be accepted.
- Redis Stream separates event ingestion from NLP inference.
