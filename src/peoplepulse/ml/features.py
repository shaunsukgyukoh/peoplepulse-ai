from __future__ import annotations

from peoplepulse.nlp.labels import LABELS

ACTIVITY_COLUMNS = [
    "job_site_events",
    "job_site_seconds",
    "job_site_active_days",
    "web_search_events",
    "web_search_active_days",
    "document_usage_events",
    "document_active_days",
    "document_create_events",
    "document_modify_events",
    "document_view_events",
    "after_hours_search_ratio",
    "after_hours_document_ratio",
    "weekend_search_ratio",
    "weekend_document_ratio",
]

SLACK_COLUMNS: list[str] = []
for window in (7, 30, 90):
    SLACK_COLUMNS.extend(
        [
            f"message_count_{window}d",
            f"active_days_{window}d",
            f"message_rate_{window}d",
        ]
    )
    SLACK_COLUMNS.extend(f"{label}_mean_{window}d" for label in LABELS)
    SLACK_COLUMNS.append(f"work_strain_mean_{window}d")
SLACK_COLUMNS.extend(["message_rate_delta_7d_30d", "work_strain_delta_7d_30d"])
SLACK_COLUMNS.extend(f"{label}_delta_7d_30d" for label in LABELS)

ALL_MODEL_FEATURES = [*ACTIVITY_COLUMNS, *SLACK_COLUMNS]

# These columns are valid synthetic experiment inputs but are deliberately excluded
# from the default portfolio model because they are direct job-search / intent proxies.
INTENT_PROXY_COLUMNS = {
    "job_site_events",
    "job_site_seconds",
    "job_site_active_days",
    "web_search_events",
    "web_search_active_days",
    "after_hours_search_ratio",
    "weekend_search_ratio",
}

PRIVACY_SAFE_FEATURES = [
    column for column in ALL_MODEL_FEATURES if column not in INTENT_PROXY_COLUMNS
]

IDENTIFIER_COLUMNS = [
    "canonical_employee_id_hash",
    "department_id_hash",
    "snapshot_month",
    "report_month",
]

TARGET_COLUMNS = ["attrition_30d", "attrition_60d", "attrition_90d"]


def feature_columns(feature_set: str) -> list[str]:
    if feature_set == "privacy_safe":
        return list(PRIVACY_SAFE_FEATURES)
    if feature_set == "synthetic_full":
        return list(ALL_MODEL_FEATURES)
    raise ValueError("feature_set must be privacy_safe or synthetic_full")
