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


def test_production_runtime_does_not_use_self_report() -> None:
    runtime_paths = (
        "src/peoplepulse/dashboard/employee_service.py",
        "src/peoplepulse/api/dashboard.py",
        "dashboard/app/page.tsx",
        "dashboard/lib/api.ts",
        "scripts/load_employee_directory.py",
        "data/templates/employee_directory.csv.example",
    )
    for path in runtime_paths:
        assert "self_report" not in Path(path).read_text(encoding="utf-8").lower()

    migration_runner = Path("scripts/apply_production_main_migration.py").read_text(
        encoding="utf-8"
    )
    assert "009_self_report_department_trends.sql" not in migration_runner
    assert set(TREND_WINDOWS) == {"hour", "day", "week", "month"}


def test_work_signal_trend_is_department_scoped() -> None:
    service = Path("src/peoplepulse/dashboard/employee_service.py").read_text(encoding="utf-8")
    api = Path("src/peoplepulse/api/dashboard.py").read_text(encoding="utf-8")
    assert "department_work_signal_trend" in service
    assert "d.department" in service
    assert '"departments": [' in service
    assert 'router.get("/departments/work-signals/trend")' in api
    assert "/teams/work-signals/trend" not in api


def test_organization_timeline_is_department_only_and_privacy_safe() -> None:
    service = Path("src/peoplepulse/dashboard/employee_service.py").read_text(encoding="utf-8")
    api = Path("src/peoplepulse/api/dashboard.py").read_text(encoding="utf-8")
    assert "organization_support_timeline" in service
    assert '"individual_identifiers_returned": False' in service
    assert '"raw_messages_returned": False' in service
    assert '"psychological_diagnosis": False' in service
    assert "aggregate_work_communication_signals_only" in service
    assert '"grouping": "department"' in service
    assert '"suppressed_department_count"' in service
    assert 'router.get("/organization/support-timeline")' in api
    assert 'router.get("/slack/live")' not in api
    assert 'router.get("/slack/trend")' not in api
    assert 'result.pop("slack", None)' in api
    assert "/self-report/" not in api


def test_dashboard_compares_all_eligible_departments_across_time_ranges() -> None:
    dashboard = Path("dashboard/app/page.tsx").read_text(encoding="utf-8")
    assert "departmentTimelineHeatmap" in dashboard
    assert "departmentTimelineLines" in dashboard
    assert "latestDepartmentPoints" in dashboard
    assert 'label: "60분"' in dashboard
    assert 'label: "일별"' in dashboard
    assert 'label: "주간"' in dashboard
    assert "suppressed_department_count" in dashboard
