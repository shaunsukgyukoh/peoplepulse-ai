from peoplepulse.slack.events import normalize_message_event


def test_normalize_hides_original_ids_and_redacts_text() -> None:
    body = {"event_id": "Ev123", "team_id": "T123"}
    event = {
        "type": "message",
        "user": "U123",
        "channel": "C123",
        "channel_type": "channel",
        "text": "hello <@U999> test@example.com",
        "ts": "123.456",
        "event_ts": "123.456",
    }
    result = normalize_message_event(body=body, event=event, employee_hash_key="secret-key")
    assert result is not None
    fields = result.fields
    assert fields["event_id"] == "Ev123"
    assert fields["employee_id_hash"] != "U123"
    assert fields["channel_id_hash"] != "C123"
    assert "U999" not in str(fields["text_masked"])
    assert "test@example.com" not in str(fields["text_masked"])


def test_normalize_ignores_bot_and_subtype_messages() -> None:
    body = {"event_id": "Ev123", "team_id": "T123"}
    base = {"user": "U123", "channel": "C123", "text": "hello", "ts": "1"}
    assert (
        normalize_message_event(
            body=body,
            event={**base, "bot_id": "B123"},
            employee_hash_key="secret-key",
        )
        is None
    )
    assert (
        normalize_message_event(
            body=body,
            event={**base, "subtype": "message_changed"},
            employee_hash_key="secret-key",
        )
        is None
    )
