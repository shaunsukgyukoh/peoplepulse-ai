from __future__ import annotations

import json
from pathlib import Path

from peoplepulse.config import Settings
from peoplepulse.dashboard.service import DashboardService


def test_dashboard_attrition_reference_fallback(tmp_path: Path) -> None:
    reference = {
        "feature_set_comparison": [
            {
                "feature_set": "privacy_safe",
                "selected_model": "logistic_regression",
                "average_precision": 0.12,
            }
        ],
        "privacy_safe_test": {"average_precision": 0.12, "brier_score": 0.05},
        "scope": "synthetic_demo_only",
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference), encoding="utf-8")
    settings = Settings(
        dashboard_step6_artifact_root=str(tmp_path / "missing"),
        dashboard_step6_reference_metrics_path=str(path),
    )
    result = DashboardService(settings).attrition_metrics()
    assert result["source"] == "repository_reference_metrics"
    assert result["selected_model"] == "logistic_regression"
    assert result["privacy_safe"]["average_precision"] == 0.12


def test_dashboard_shap_rank_fallback_does_not_fabricate_magnitude(tmp_path: Path) -> None:
    settings = Settings(dashboard_shap_path=str(tmp_path / "missing.csv"))
    result = DashboardService(settings).shap_importance()
    assert result["source"] == "repository_reference_rank_only"
    assert result["features"][0]["mean_abs_shap"] is None


def test_dashboard_cors_defaults_are_local_only() -> None:
    origins = Settings().dashboard_cors_origins
    assert "http://localhost:3000" in origins
    assert all("localhost" in origin or "127.0.0.1" in origin for origin in origins)
