from dataclasses import dataclass
from datetime import UTC, datetime

from peoplepulse.privacy.redaction import redact_basic_pii
from peoplepulse.security.identifiers import pseudonymize


@dataclass(frozen=True)
class NormalizedSlackEvent:
    fields: dict[str, str | int]


def normalize_message_event(
    *, body: dict,
    event: dict,
    employee_hash_key: str,
) -> NormalizedSlackEvent | None:
    """Normalize a human-authored Slack message into a privacy-reduced queue record."""
    event_id = str(body.get("event_id", "")).strip()
    user_id = str(event.get("user", "")).strip()
    channel_id = str(event.get("channel", "")).strip()
    text = str(event.get("text", "")).strip()

    # Ignore bot/system/edited/deleted events for the STEP 2 MVP.
    if not event_id or not user_id or not channel_id or not text:
        return None
    if event.get("subtype") is not None or event.get("bot_id") or event.get("app_id"):
        return None

    team_id = str(body.get("team_id", "unknown"))
    channel_type = str(event.get("channel_type", "unknown"))
    event_ts = str(event.get("event_ts") or event.get("ts") or "")
    message_ts = str(event.get("ts", ""))
    thread_ts = str(event.get("thread_ts", ""))

    masked_text = redact_basic_pii(text)
    fields: dict[str, str | int] = {
        "schema_version": "1",
        "source": "slack",
        "event_id": event_id,
        "team_id_hash": pseudonymize(team_id, employee_hash_key, namespace="team"),
        "channel_id_hash": pseudonymize(channel_id, employee_hash_key, namespace="channel"),
        "employee_id_hash": pseudonymize(user_id, employee_hash_key, namespace="employee"),
        "channel_type": channel_type,
        "event_ts": event_ts,
        "message_ts": message_ts,
        "thread_id_hash": (
            pseudonymize(f"{channel_id}:{thread_ts}", employee_hash_key, namespace="thread")
            if thread_ts
            else ""
        ),
        "text_masked": masked_text,
        "text_length": len(masked_text),
        "received_at": datetime.now(UTC).isoformat(),
    }
    return NormalizedSlackEvent(fields=fields)
