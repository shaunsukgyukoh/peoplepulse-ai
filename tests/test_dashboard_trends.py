from pathlib import Path

import pytest

from peoplepulse.dashboard.employee_service import (
    TIMELINE_GROUP_EXPRESSIONS,
    TREND_WINDOWS,
    _timeline_group_expression,
    _trend_window,
)


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


@pytest.mark.parametrize(
    ("group_by", "expected_sql"),
    [
        ("overall", "'전체'"),
        ("department", "d.department"),
        ("job_title", "d.job_title"),
    ],
)
def test_timeline_grouping_contract(group_by: str, expected_sql: str) -> None:
    assert expected_sql in _timeline_group_expression(group_by)
    assert set(TIMELINE_GROUP_EXPRESSIONS) == {"overall", "department", "job_title"}


def test_timeline_grouping_rejects_unknown_scope() -> None:
    with pytest.raises(ValueError, match="unsupported timeline grouping"):
        _timeline_group_expression("employee")


def test_self_report_history_migration_has_no_slack_inference_path() -> None:
    migration = Path(
        "infra/postgres/migrations/009_self_report_department_trends.sql"
    ).read_text(encoding="utf-8")
    assert "employee_self_report_history" in migration
    assert "Voluntary employee-provided self-report history" in migration
    assert "message_nlp_signal" not in migration
    assert set(TREND_WINDOWS) == {"hour", "day", "week", "month"}


def test_work_signal_trend_is_department_scoped() -> None:
    service = Path("src/peoplepulse/dashboard/employee_service.py").read_text(encoding="utf-8")
    api = Path("src/peoplepulse/api/dashboard.py").read_text(encoding="utf-8")
    assert "department_work_signal_trend" in service
    assert "d.department" in service
    assert '"departments": [' in service
    assert 'router.get("/departments/work-signals/trend")' in api
    assert "/teams/work-signals/trend" not in api


def test_organization_timeline_has_privacy_safe_sources_and_scopes() -> None:
    service = Path("src/peoplepulse/dashboard/employee_service.py").read_text(encoding="utf-8")
    api = Path("src/peoplepulse/api/dashboard.py").read_text(encoding="utf-8")
    assert "organization_support_timeline" in service
    assert '"individual_identifiers_returned": False' in service
    assert '"psychological_diagnosis": False' in service
    assert "voluntary_employee_self_report_only" in service
    assert "aggregate_work_communication_signals_only" in service
    assert 'if work_signals_exist and group_by == "department"' in service
    assert '"work_signals": ["department"]' in service
    assert 'router.get("/organization/support-timeline")' in api
