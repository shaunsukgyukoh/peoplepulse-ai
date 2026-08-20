import pandas as pd
import pytest

from peoplepulse.config import Settings
from peoplepulse.monitoring.drift import extract_drift_count, select_recent_month_windows


def test_recent_month_windows_do_not_overlap():
    frame = pd.DataFrame({
        "snapshot_month": pd.date_range("2025-01-01", periods=12, freq="MS"),
        "x": range(12),
    })
    result = select_recent_month_windows(
        frame,
        month_column="snapshot_month",
        reference_months=6,
        current_months=3,
    )
    assert set(result.reference["snapshot_month"]).isdisjoint(set(result.current["snapshot_month"]))
    assert result.reference_period == "2025-04..2025-09"
    assert result.current_period == "2025-10..2025-12"


def test_extract_evidently_drift_count_is_layout_tolerant():
    payload = {
        "metrics": [
            {
                "metric_id": "DriftedColumnsCount()",
                "value": {"count": 3, "share": 0.25},
            }
        ]
    }
    assert extract_drift_count(payload) == (3, 0.25)


def test_synthetic_monitoring_blocked_in_production():
    settings = Settings(
        _env_file=None,
        app_env="production",
        mlops_monitoring_scope="synthetic_demo",
    )
    with pytest.raises(RuntimeError, match="synthetic_demo"):
        settings.validate_mlops_runtime()


def test_aggregate_monitoring_allowed_in_production():
    settings = Settings(
        _env_file=None,
        app_env="production",
        mlops_monitoring_scope="aggregate",
    )
    settings.validate_mlops_runtime()
