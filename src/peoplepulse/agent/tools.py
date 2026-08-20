from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import psycopg
from langchain_core.tools import tool
from psycopg.rows import dict_row

from peoplepulse.config import Settings
from peoplepulse.dashboard.service import DashboardService
from peoplepulse.security.identifiers import pseudonymize


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _table_exists(connection: psycopg.Connection, name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (name,))
        row = cursor.fetchone()
    return bool(row and row["exists"])


def build_tools(settings: Settings, *, scope: str):
    dashboard = DashboardService(settings)

    @tool
    def get_executive_overview() -> str:
        """현재 PeoplePulse 전체 상태, 최근 Slack 파생 신호, 최신 월간 보고서, NLP/모델 평가 요약을 조회한다."""
        return _json({"source": "dashboard.executive_overview", "data": dashboard.executive_overview()})

    @tool
    def get_slack_signal_trend(minutes: int = 60) -> str:
        """최근 5~1440분의 집계된 Slack NLP 신호 추세를 조회한다. 원문 메시지는 반환하지 않는다."""
        minutes = max(5, min(int(minutes), 1440))
        return _json(
            {
                "source": "features.message_nlp_signal.aggregate",
                "minutes": minutes,
                "current": dashboard.slack_live(),
                "trend": dashboard.slack_trend(minutes=minutes),
            }
        )

    @tool
    def get_feature_store_cohort_summary(months: int = 6) -> str:
        """최근 월별 production-safe 부서/코호트 Feature Store 통계를 조회한다. 부서 식별자는 반환하지 않는다."""
        months = max(1, min(int(months), 24))
        with psycopg.connect(settings.postgres_dsn, row_factory=dict_row) as connection:
            if not _table_exists(connection, "features.department_monthly_fusion"):
                return _json({"source": "features.department_monthly_fusion", "status": "not_ready"})
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT report_month::text,
                           COUNT(*)::bigint AS cohort_rows,
                           SUM(cohort_employee_count)::bigint AS cohort_employee_total,
                           AVG(message_rate_30d)::double precision AS message_rate_30d,
                           AVG(work_strain_mean_30d)::double precision AS work_strain_mean_30d,
                           AVG(work_strain_delta_7d_30d)::double precision AS work_strain_delta_7d_30d,
                           AVG(document_usage_events)::double precision AS document_usage_events,
                           AVG(after_hours_document_ratio)::double precision AS after_hours_document_ratio
                    FROM features.department_monthly_fusion
                    GROUP BY report_month
                    ORDER BY report_month DESC
                    LIMIT %s
                    """,
                    (months,),
                )
                rows = cursor.fetchall()
        return _json({"source": "features.department_monthly_fusion.aggregate", "rows": rows})

    @tool
    def get_monitoring_drift_summary() -> str:
        """STEP 8 Evidently monitoring의 최신 data drift 및 synthetic model performance drift 요약을 조회한다."""
        path = Path(settings.mlops_monitoring_summary_path)
        if not path.exists():
            return _json({"source": "artifacts.monitoring.latest_summary", "status": "not_ready"})
        return _json({"source": "artifacts.monitoring.latest_summary", "data": json.loads(path.read_text(encoding="utf-8"))})

    @tool
    def get_retention_model_evaluation() -> str:
        """STEP 6 synthetic-only retention model의 temporal test, calibration, ablation 평가를 조회한다."""
        return _json({"source": "step6.synthetic_retention_evaluation", "data": dashboard.attrition_metrics()})

    @tool
    def get_shap_global_importance() -> str:
        """STEP 6 synthetic retention model의 global SHAP feature importance를 조회한다. 개인 설명이 아니다."""
        return _json({"source": "step6.synthetic_shap_global", "data": dashboard.shap_importance()})

    @tool
    def get_nlp_model_performance() -> str:
        """STEP 3 Korean workplace-message NLP 후보들의 Macro-F1, precision, recall, latency 평가를 조회한다."""
        return _json({"source": "step3.nlp_benchmark", "models": dashboard.nlp_metrics()})

    @tool
    def get_mlflow_experiments() -> str:
        """로컬 MLflow의 experiment 목록을 read-only REST API로 조회한다."""
        url = settings.mlflow_tracking_uri.rstrip("/") + "/api/2.0/mlflow/experiments/search?max_results=50"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return _json({"source": "mlflow.experiments", "status": "unavailable", "error": str(exc)})
        experiments = [
            {
                "experiment_id": row.get("experiment_id"),
                "name": row.get("name"),
                "lifecycle_stage": row.get("lifecycle_stage"),
            }
            for row in payload.get("experiments", [])
        ]
        return _json({"source": "mlflow.experiments", "experiments": experiments})

    @tool
    def get_mlflow_recent_runs(experiment_name: str = "PeoplePulse-Monitoring-Step8", limit: int = 10) -> str:
        """PeoplePulse MLflow experiment의 최근 run과 기록된 metric을 read-only REST API로 조회한다."""
        limit = max(1, min(int(limit), 20))
        base = settings.mlflow_tracking_uri.rstrip("/")
        try:
            with urllib.request.urlopen(base + "/api/2.0/mlflow/experiments/search?max_results=100", timeout=5) as response:
                experiments = json.loads(response.read().decode("utf-8")).get("experiments", [])
            match = next((row for row in experiments if row.get("name") == experiment_name), None)
            if not match:
                return _json({"source": "mlflow.runs", "status": "experiment_not_found", "experiment_name": experiment_name})
            body = json.dumps({
                "experiment_ids": [match["experiment_id"]],
                "max_results": limit,
                "order_by": ["attributes.start_time DESC"],
            }).encode("utf-8")
            request = urllib.request.Request(
                base + "/api/2.0/mlflow/runs/search",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return _json({"source": "mlflow.runs", "status": "unavailable", "error": str(exc)})
        rows = []
        for run in payload.get("runs", []):
            info = run.get("info", {})
            data = run.get("data", {})
            run_name = next((t.get("value") for t in data.get("tags", []) if t.get("key") == "mlflow.runName"), None)
            metrics = {m.get("key"): m.get("value") for m in data.get("metrics", []) if m.get("key")}
            rows.append({
                "run_id": info.get("run_id"),
                "run_name": run_name,
                "status": info.get("status"),
                "start_time": info.get("start_time"),
                "metrics": metrics,
            })
        return _json({"source": "mlflow.runs", "experiment_name": experiment_name, "runs": rows})

    tools = [
        get_executive_overview,
        get_slack_signal_trend,
        get_feature_store_cohort_summary,
        get_monitoring_drift_summary,
        get_retention_model_evaluation,
        get_shap_global_importance,
        get_nlp_model_performance,
        get_mlflow_experiments,
        get_mlflow_recent_runs,
    ]

    if scope == "synthetic_demo":
        @tool
        def get_synthetic_employee_snapshot(demo_key: str, report_month: str) -> str:
            """synthetic_demo 전용으로 demo-001 같은 synthetic canonical key의 월별 feature snapshot을 조회한다."""
            if not demo_key.startswith("demo-"):
                return _json({"source": "features.synthetic_employee_retention_feature", "error": "demo-* synthetic key만 허용"})
            canonical_hash = pseudonymize(demo_key, settings.employee_hash_key, namespace="canonical-employee")
            with psycopg.connect(settings.postgres_dsn, row_factory=dict_row) as connection:
                if not _table_exists(connection, "features.synthetic_employee_retention_feature"):
                    return _json({"source": "features.synthetic_employee_retention_feature", "status": "not_ready"})
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT report_month::text,
                               message_rate_7d, message_rate_30d, message_rate_90d,
                               work_strain_mean_7d, work_strain_mean_30d, work_strain_mean_90d,
                               work_strain_delta_7d_30d,
                               satisfied_mean_30d, overloaded_mean_30d, disengaged_mean_30d,
                               document_usage_events, after_hours_document_ratio,
                               has_activity_data, has_slack_data
                        FROM features.synthetic_employee_retention_feature
                        WHERE canonical_employee_id_hash = %s
                          AND report_month = %s::date
                        """,
                        (canonical_hash, f"{report_month}-01" if len(report_month) == 7 else report_month),
                    )
                    row = cursor.fetchone()
            return _json({"source": "features.synthetic_employee_retention_feature", "scope": "synthetic_demo_only", "demo_key": demo_key, "data": row})

        tools.append(get_synthetic_employee_snapshot)

    return tools
