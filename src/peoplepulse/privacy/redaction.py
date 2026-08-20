import re

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
_SLACK_LINK = re.compile(r"<https?://[^>|]+(?:\|[^>]+)?>", re.IGNORECASE)
_SLACK_USER = re.compile(r"<@[A-Z0-9]+>")
_SLACK_CHANNEL = re.compile(r"<#[A-Z0-9]+(?:\|[^>]+)?>")
_PHONE = re.compile(r"(?<!\d)(?:\+?82[- .]?)?(?:0?1[016789])[- .]?\d{3,4}[- .]?\d{4}(?!\d)")


def redact_basic_pii(text: str) -> str:
    """Redact common identifiers before a Slack message enters Redis.

    This is intentionally conservative and will be extended in STEP 3 with a
    stronger PII pipeline. It avoids logging or persisting the unredacted text.
    """
    masked = _SLACK_LINK.sub("[URL]", text)
    masked = _URL.sub("[URL]", masked)
    masked = _EMAIL.sub("[EMAIL]", masked)
    masked = _PHONE.sub("[PHONE]", masked)
    masked = _SLACK_USER.sub("[USER]", masked)
    masked = _SLACK_CHANNEL.sub("[CHANNEL]", masked)
    return masked.strip()
