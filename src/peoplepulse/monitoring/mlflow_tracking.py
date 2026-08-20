from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _client(tracking_uri: str):
    import mlflow
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow


def log_monitoring_snapshot(
    summary: dict[str, Any],
    *,
    tracking_uri: str,
    experiment_name: str,
    artifact_root: str | Path,
) -> str:
    mlflow = _client(tracking_uri)
    mlflow.set_experiment(experiment_name)
    drift = summary.get("data_drift", {})
    perf = summary.get("model_performance", {})
    with mlflow.start_run(run_name=f"drift-{summary.get('scope', 'unknown')}") as run:
        mlflow.set_tags({
            "peoplepulse.stage": "step8-monitoring",
            "peoplepulse.scope": str(summary.get("scope")),
            "peoplepulse.privacy_contract": str(summary.get("privacy_contract")),
        })
        mlflow.log_params({
            "feature_set": str(summary.get("feature_set")),
            "reference_period": str(drift.get("reference_period")),
            "current_period": str(drift.get("current_period")),
            "drift_threshold": drift.get("threshold"),
        })
        metrics: dict[str, float] = {}
        for key in ("reference_rows", "current_rows", "monitored_features", "drifted_features", "drift_share"):
            value = drift.get(key)
            if value is not None:
                metrics[f"data_drift.{key}"] = float(value)
        if perf.get("available"):
            for window in ("reference", "current"):
                for key, value in perf.get(window, {}).items():
                    if isinstance(value, (int, float)):
                        metrics[f"model.{window}.{key}"] = float(value)
            for key, value in perf.get("delta", {}).items():
                if value is not None:
                    metrics[f"model.delta.{key}"] = float(value)
        if metrics:
            mlflow.log_metrics(metrics)
        latest = Path(artifact_root) / "latest_summary.json"
        report = Path(artifact_root) / "latest_evidently_data_drift.html"
        if latest.exists():
            mlflow.log_artifact(str(latest), artifact_path="monitoring")
        if report.exists():
            mlflow.log_artifact(str(report), artifact_path="monitoring")
        return run.info.run_id


def import_step6_experiments(
    *, tracking_uri: str,
    artifact_root: str | Path = "artifacts/ml/step6",
    experiment_name: str = "PeoplePulse-Attrition-Step6",
) -> list[str]:
    mlflow = _client(tracking_uri)
    root = Path(artifact_root)
    mlflow.set_experiment(experiment_name)
    run_ids: list[str] = []
    for feature_set in ("privacy_safe", "synthetic_full"):
        folder = root / feature_set
        evaluation = folder / "evaluation.json"
        if not evaluation.exists():
            continue
        payload = json.loads(evaluation.read_text(encoding="utf-8"))
        with mlflow.start_run(run_name=f"step6-{feature_set}") as run:
            mlflow.set_tags({
                "peoplepulse.stage": "step6-import",
                "peoplepulse.scope": "synthetic_demo_only",
                "peoplepulse.feature_set": feature_set,
            })
            mlflow.log_params({
                "selected_model": payload.get("selected_model"),
                "target": payload.get("target"),
                "calibration_method": payload.get("calibration_method"),
                "selection_metric": payload.get("selection_metric"),
            })
            metrics: dict[str, float] = {}
            for prefix in ("test_raw", "test_calibrated"):
                for key, value in payload.get(prefix, {}).items():
                    if isinstance(value, (int, float)):
                        metrics[f"{prefix}.{key}"] = float(value)
            if metrics:
                mlflow.log_metrics(metrics)
            for file in folder.iterdir():
                if file.is_file() and file.suffix in {".json", ".csv"}:
                    mlflow.log_artifact(str(file), artifact_path=f"step6/{feature_set}")
            shap_dir = folder / "shap"
            if shap_dir.exists():
                mlflow.log_artifacts(str(shap_dir), artifact_path=f"step6/{feature_set}/shap")
            run_ids.append(run.info.run_id)
    return run_ids


def import_nlp_benchmark(
    *,
    tracking_uri: str,
    metrics_path: str | Path = "docs/experiment-results/nlp_model_comparison_step3_1.json",
    experiment_name: str = "PeoplePulse-NLP-Step3",
) -> list[str]:
    mlflow = _client(tracking_uri)
    path = Path(metrics_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("models", payload.get("results", []))
    if isinstance(rows, dict):
        rows = [dict({"model": key}, **value) for key, value in rows.items() if isinstance(value, dict)]
    mlflow.set_experiment(experiment_name)
    ids: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("model") or row.get("name") or "nlp-model")
        with mlflow.start_run(run_name=name) as run:
            mlflow.set_tags({"peoplepulse.stage": "step3-import", "peoplepulse.scope": "work-message-nlp"})
            numeric = {key: float(value) for key, value in row.items() if isinstance(value, (int, float))}
            text = {key: str(value) for key, value in row.items() if isinstance(value, str) and key not in {"model", "name"}}
            if numeric:
                mlflow.log_metrics(numeric)
            if text:
                mlflow.log_params(text)
            mlflow.log_artifact(str(path), artifact_path="step3")
            ids.append(run.info.run_id)
    return ids
