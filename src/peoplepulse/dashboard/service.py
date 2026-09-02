from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from peoplepulse.config import Settings

# ruff: noqa: E501

SIGNALS = (
    "satisfied",
    "neutral",
    "frustrated",
    "angry",
    "dissatisfied",
    "overloaded",
    "conflict",
    "disengaged",
)

WORK_STRAIN_SIGNALS = (
    "frustrated",
    "angry",
    "dissatisfied",
    "overloaded",
    "conflict",
    "disengaged",
)


def _read_json(path: str | Path) -> Any:
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def _read_shap_csv(path: str | Path, *, limit: int = 15) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows[:limit]:
        try:
            value = float(row.get("mean_abs_shap", 0.0))
        except (TypeError, ValueError):
            value = 0.0
        result.append({"feature": row.get("feature", "unknown"), "mean_abs_shap": value})
    return result


@dataclass
class DashboardService:
    settings: Settings

    def _connect(self):
        return psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row)

    @staticmethod
    def _table_exists(connection: psycopg.Connection, table_name: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (table_name,))
            row = cursor.fetchone()
        return bool(row and row["exists"])

    def slack_live(self) -> dict[str, Any]:
        fallback = {
            "message_count": 0,
            "avg_inference_ms": 0.0,
            "work_strain": 0.0,
            "signals": {signal: 0.0 for signal in SIGNALS},
            "model_name": None,
            "model_device": None,
            "last_message_at": None,
        }
        with self._connect() as connection:
            if not self._table_exists(connection, "features.message_nlp_signal"):
                return fallback
            signal_select = ",\n".join(
                f"COALESCE(AVG({signal}), 0)::double precision AS {signal}" for signal in SIGNALS
            )
            strain_expr = " + ".join(WORK_STRAIN_SIGNALS)
            query = f"""
                SELECT
                    COUNT(*)::bigint AS message_count,
                    COALESCE(AVG(inference_ms), 0)::double precision AS avg_inference_ms,
                    COALESCE(AVG(({strain_expr}) / {len(WORK_STRAIN_SIGNALS)}.0), 0)::double precision AS work_strain,
                    {signal_select},
                    (ARRAY_AGG(model_name ORDER BY COALESCE(message_ts, received_at) DESC))[1] AS model_name,
                    (ARRAY_AGG(model_device ORDER BY COALESCE(message_ts, received_at) DESC))[1] AS model_device,
                    MAX(COALESCE(message_ts, received_at)) AS last_message_at
                FROM features.message_nlp_signal
                WHERE COALESCE(message_ts, received_at) >= NOW() - INTERVAL '15 minutes'
            """
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
        if not row:
            return fallback
        return {
            "message_count": int(row["message_count"] or 0),
            "avg_inference_ms": float(row["avg_inference_ms"] or 0.0),
            "work_strain": float(row["work_strain"] or 0.0),
            "signals": {signal: float(row[signal] or 0.0) for signal in SIGNALS},
            "model_name": row["model_name"],
            "model_device": row["model_device"],
            "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
        }

    def slack_trend(self, *, minutes: int = 60) -> list[dict[str, Any]]:
        minutes = max(5, min(minutes, 24 * 60))
        with self._connect() as connection:
            if not self._table_exists(connection, "features.message_nlp_signal"):
                return []
            strain_expr = " + ".join(WORK_STRAIN_SIGNALS)
            query = f"""
                SELECT
                    DATE_TRUNC('minute', COALESCE(message_ts, received_at)) AS bucket,
                    COUNT(*)::bigint AS message_count,
                    AVG(satisfied)::double precision AS satisfied,
                    AVG(frustrated)::double precision AS frustrated,
                    AVG(overloaded)::double precision AS overloaded,
                    AVG(disengaged)::double precision AS disengaged,
                    AVG(({strain_expr}) / {len(WORK_STRAIN_SIGNALS)}.0)::double precision AS work_strain,
                    AVG(inference_ms)::double precision AS avg_inference_ms
                FROM features.message_nlp_signal
                WHERE COALESCE(message_ts, received_at) >= NOW() - (%s * INTERVAL '1 minute')
                GROUP BY 1
                ORDER BY 1
            """
            with connection.cursor() as cursor:
                cursor.execute(query, (minutes,))
                rows = cursor.fetchall()
        return [
            {
                **row,
                "bucket": row["bucket"].isoformat(),
                "message_count": int(row["message_count"]),
                "satisfied": float(row["satisfied"] or 0.0),
                "frustrated": float(row["frustrated"] or 0.0),
                "overloaded": float(row["overloaded"] or 0.0),
                "disengaged": float(row["disengaged"] or 0.0),
                "work_strain": float(row["work_strain"] or 0.0),
                "avg_inference_ms": float(row["avg_inference_ms"] or 0.0),
            }
            for row in rows
        ]

    def latest_report(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            if not self._table_exists(connection, "audit.activity_report_set_batch"):
                return None
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        batch_id::text,
                        report_month::text,
                        period_start::text,
                        period_end::text,
                        privacy_mode,
                        status,
                        input_rows,
                        duplicate_rows_removed,
                        privacy_excluded_rows,
                        department_feature_rows,
                        synthetic_employee_feature_rows,
                        suppressed_departments,
                        created_at
                    FROM audit.activity_report_set_batch
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["created_at"] = row["created_at"].isoformat()
        return result

    def activity_summary(self) -> dict[str, Any]:
        result = {
            "department_rows": 0,
            "synthetic_employee_rows": 0,
            "latest_month": None,
        }
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if self._table_exists(connection, "features.department_monthly_activity"):
                    cursor.execute(
                        "SELECT COUNT(*)::bigint AS rows, MAX(report_month)::text AS month FROM features.department_monthly_activity"
                    )
                    row = cursor.fetchone()
                    result["department_rows"] = int(row["rows"] or 0)
                    result["latest_month"] = row["month"]
                if self._table_exists(connection, "features.synthetic_employee_monthly_activity"):
                    cursor.execute(
                        "SELECT COUNT(*)::bigint AS rows, MAX(report_month)::text AS month FROM features.synthetic_employee_monthly_activity"
                    )
                    row = cursor.fetchone()
                    result["synthetic_employee_rows"] = int(row["rows"] or 0)
                    result["latest_month"] = result["latest_month"] or row["month"]
        return result

    def attrition_metrics(self) -> dict[str, Any]:
        root = Path(self.settings.dashboard_step6_artifact_root)
        comparison = _read_json(root / "feature_set_comparison.json")
        evaluation = _read_json(root / "privacy_safe" / "evaluation.json")
        calibration = _read_json(root / "privacy_safe" / "calibration_points.json")

        if comparison and evaluation:
            return {
                "source": "local_experiment_artifacts",
                "scope": "synthetic_demo_only",
                "feature_sets": comparison,
                "selected_model": evaluation.get("selected_model"),
                "privacy_safe": evaluation.get("test_calibrated", {}),
                "privacy_safe_raw": evaluation.get("test_raw", {}),
                "split": evaluation.get("split", {}),
                "calibration": calibration or {},
            }

        reference = _read_json(self.settings.dashboard_step6_reference_metrics_path) or {}
        feature_sets = reference.get("feature_set_comparison", [])
        selected = next((x for x in feature_sets if x.get("feature_set") == "privacy_safe"), {})
        return {
            "source": "repository_reference_metrics",
            "scope": reference.get("scope", "synthetic_demo_only"),
            "feature_sets": feature_sets,
            "selected_model": selected.get("selected_model"),
            "privacy_safe": reference.get("privacy_safe_test", {}),
            "privacy_safe_raw": {},
            "split": {},
            "calibration": {},
        }

    def nlp_metrics(self) -> list[dict[str, Any]]:
        data = _read_json(self.settings.dashboard_nlp_metrics_path)
        return data if isinstance(data, list) else []

    def shap_importance(self) -> dict[str, Any]:
        rows = _read_shap_csv(self.settings.dashboard_shap_path, limit=15)
        if rows:
            return {"source": "local_experiment_artifacts", "features": rows}
        reference = [
            "active_days_90d",
            "overloaded_mean_90d",
            "dissatisfied_mean_90d",
            "satisfied_mean_30d",
            "document_active_days",
            "satisfied_mean_7d",
            "dissatisfied_mean_30d",
            "dissatisfied_mean_7d",
            "angry_mean_90d",
            "message_rate_90d",
        ]
        # Rank-only fallback: intentionally no fabricated SHAP magnitude.
        return {
            "source": "repository_reference_rank_only",
            "features": [
                {"feature": name, "mean_abs_shap": None, "rank": index + 1}
                for index, name in enumerate(reference)
            ],
        }

    def executive_overview(self) -> dict[str, Any]:
        slack = self.slack_live()
        report = self.latest_report()
        activity = self.activity_summary()
        attrition = self.attrition_metrics()
        nlp = self.nlp_metrics()
        selected_nlp = nlp[0] if nlp else {}
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "slack": slack,
            "latest_report": report,
            "activity": activity,
            "nlp_model": selected_nlp,
            "attrition_model": {
                "scope": attrition.get("scope"),
                "selected_model": attrition.get("selected_model"),
                **attrition.get("privacy_safe", {}),
            },
            "privacy": {
                "production_scope": "department_or_cohort_only",
                "employee_level_attrition_scope": "synthetic_demo_only",
                "raw_slack_text_persisted": False,
                "raw_activity_text_persisted": False,
            },
        }
