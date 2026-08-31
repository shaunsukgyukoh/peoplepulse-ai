import asyncio
from types import SimpleNamespace

from fastapi.sse import ServerSentEvent

from peoplepulse.api import dashboard as dashboard_api


def test_slack_stream_yields_json_event_without_wrapping_a_coroutine(monkeypatch) -> None:
    payload = {
        "message_count": 1,
        "avg_inference_ms": 12.5,
        "work_strain": 0.25,
        "signals": {"satisfied": 0.75},
        "model_name": "test-model",
        "model_device": "cpu",
        "last_message_at": "2026-08-31T00:00:00+00:00",
    }

    class FakeDashboardService:
        def slack_live(self) -> dict:
            return payload

    monkeypatch.setattr(dashboard_api, "_service", FakeDashboardService)
    monkeypatch.setattr(
        dashboard_api,
        "get_settings",
        lambda: SimpleNamespace(dashboard_stream_interval_seconds=0.01),
    )

    async def first_event() -> ServerSentEvent:
        stream = dashboard_api.slack_stream()
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    event = asyncio.run(first_event())

    assert event.event == "slack_signal"
    assert event.data == payload
