from peoplepulse.privacy.redaction import redact_basic_pii


def test_redacts_common_identifiers() -> None:
    text = "<@U123> email me at user@example.com or https://example.com and 010-1234-5678"
    masked = redact_basic_pii(text)
    assert "U123" not in masked
    assert "user@example.com" not in masked
    assert "https://example.com" not in masked
    assert "010-1234-5678" not in masked
    assert "[USER]" in masked
    assert "[EMAIL]" in masked
    assert "[URL]" in masked
    assert "[PHONE]" in masked
