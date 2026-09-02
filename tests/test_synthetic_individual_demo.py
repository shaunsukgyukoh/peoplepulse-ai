from __future__ import annotations

import inspect
from pathlib import Path

from peoplepulse.config import Settings
from peoplepulse.dashboard.employee_service import EmployeeDashboardService
from peoplepulse.dashboard.synthetic_demo import (
    load_structural_text_statistics,
    load_synthetic_personas,
)


def test_committed_synthetic_catalog_preserves_fictional_names() -> None:
    personas = load_synthetic_personas(
        "data/synthetic/identity/canonical_employee_map.csv",
        secret="synthetic-demo-secret-for-tests",
    )

    assert [row["employee_name"] for row in personas] == ["김가람", "이도윤", "박서진"]
    assert all(row["activity_employee_id_hash"] != row["employee_name"] for row in personas)


def test_structural_text_statistics_return_counts_without_raw_text() -> None:
    result = load_structural_text_statistics(
        "data/synthetic/dashboard/individual_activity_messages.csv"
    )

    assert set(result) == {"demo-001", "demo-002", "demo-003"}
    assert result["demo-001"]["message_count"] == 6
    assert result["demo-001"]["question_mark_count"] == 1
    assert result["demo-002"]["exclamation_mark_count"] == 1
    assert result["demo-003"]["polite_ending_message_ratio"] == 1.0
    assert "text" not in result["demo-001"]
    assert result["demo-001"]["top_terms"]


def test_synthetic_individual_demo_is_closed_outside_development_demo_mode() -> None:
    aggregate = EmployeeDashboardService(
        Settings(app_env="development", activity_privacy_mode="aggregate")
    ).synthetic_individual_activity()
    production = EmployeeDashboardService(
        Settings(app_env="production", activity_privacy_mode="synthetic_demo")
    ).synthetic_individual_activity()

    assert aggregate["enabled"] is False
    assert production["enabled"] is False
    assert aggregate["personas"] == []
    assert production["personas"] == []


def test_synthetic_demo_does_not_read_individual_slack_or_nlp_features() -> None:
    source = inspect.getsource(EmployeeDashboardService.synthetic_individual_activity)
    dashboard = Path("dashboard/app/page.tsx").read_text(encoding="utf-8")

    assert "message_nlp_signal" not in source
    assert "synthetic_employee_monthly_slack_signal" not in source
    assert '"individual_slack_nlp_visible": False' in source
    assert '"sentiment_or_tone_inference": False' in source
    assert "개인별 Slack NLP 0건" in dashboard
    assert "긍정/부정/중립 비율" in dashboard
