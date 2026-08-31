from pathlib import Path

import pytest

from peoplepulse.dashboard.employee_service import TREND_WINDOWS, _trend_window


@pytest.mark.parametrize(
    ("granularity", "bucket", "interval", "window"),
    [
        ("hour", "hour", "24 hours", "last_24_hours"),
        ("day", "day", "30 days", "last_30_days"),
        ("week", "week", "12 weeks", "last_12_weeks"),
        ("month", "month", "12 months", "last_12_months"),
    ],
)
def test_trend_window_contract(
    granularity: str,
    bucket: str,
    interval: str,
    window: str,
) -> None:
    assert _trend_window(granularity) == (bucket, interval, window)


def test_trend_window_rejects_unknown_granularity() -> None:
    with pytest.raises(ValueError, match="unsupported trend granularity"):
        _trend_window("quarter")


def test_self_report_history_migration_has_no_slack_inference_path() -> None:
    migration = Path("infra/postgres/migrations/009_self_report_team_trends.sql").read_text(
        encoding="utf-8"
    )
    assert "employee_self_report_history" in migration
    assert "Voluntary employee-provided self-report history" in migration
    assert "message_nlp_signal" not in migration
    assert set(TREND_WINDOWS) == {"hour", "day", "week", "month"}
