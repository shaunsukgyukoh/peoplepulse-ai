from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from peoplepulse.config import Settings
from peoplepulse.ml.features import feature_columns
from peoplepulse.ml.metrics import ranking_metrics


@dataclass(frozen=True)
class MonitoringWindows:
    reference: pd.DataFrame
    current: pd.DataFrame
    reference_period: str
    current_period: str


def _month_strings(values: Iterable[object]) -> list[str]:
    parsed = pd.to_datetime(pd.Series(list(values)), errors="coerce")
    return sorted({value.strftime("%Y-%m") for value in parsed.dropna()})


def select_recent_month_windows(
    frame: pd.DataFrame,
    *,
    month_column: str,
    reference_months: int,
    current_months: int,
) -> MonitoringWindows:
    if reference_months < 1 or current_months < 1:
        raise ValueError("reference_months and current_months must both be >= 1")
    data = frame.copy()
    data[month_column] = pd.to_datetime(data[month_column], errors="coerce").dt.to_period("M").dt.to_timestamp()
    data = data[data[month_column].notna()].copy()
    months = sorted(data[month_column].drop_duplicates().tolist())
    required = reference_months + current_months
    if len(months) < required:
        raise ValueError(f"Need at least {required} unique months, found {len(months)}")
    current_values = months[-current_months:]
    reference_values = months[-required:-current_months]
    reference = data[data[month_column].isin(reference_values)].copy()
    current = data[data[month_column].isin(current_values)].copy()
    if reference.empty or current.empty:
        raise ValueError("Reference/current monitoring windows must both be non-empty")
    reference_period = f"{reference_values[0]:%Y-%m}..{reference_values[-1]:%Y-%m}"
    current_period = f"{current_values[0]:%Y-%m}..{current_values[-1]:%Y-%m}"
    return MonitoringWindows(reference, current, reference_period, current_period)


def _recursive_drift_count(payload: Any, context: str = "") -> tuple[int | None, float | None]:
    if isinstance(payload, dict):
        local_context = context + " " + " ".join(
            str(payload.get(key, ""))
            for key in ("metric", "metric_id", "name", "type", "metric_type", "display_name")
        )
        value = payload.get("value")
        if "DriftedColumnsCount" in local_context and isinstance(value, dict):
            if "count" in value and "share" in value:
                return int(value["count"]), float(value["share"])
        if "DriftedColumnsCount" in local_context and "count" in payload and "share" in payload:
            return int(payload["count"]), float(payload["share"])
        for key, child in payload.items():
            found = _recursive_drift_count(child, local_context + " " + str(key))
            if found[0] is not None:
                return found
    elif isinstance(payload, list):
        for child in payload:
            found = _recursive_drift_count(child, context)
            if found[0] is not None:
                return found
    return None, None


def extract_drift_count(payload: dict[str, Any]) -> tuple[int | None, float | None]:
    """Extract Evidently DriftedColumnsCount without coupling to one JSON layout."""
    return _recursive_drift_count(payload)


def _safe_float(value: float | int | np.floating | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _performance(frame: pd.DataFrame) -> dict[str, float | int] | None:
    if frame.empty or "attrition_90d" not in frame or "calibrated_probability" not in frame:
        return None
    y = pd.to_numeric(frame["attrition_90d"], errors="coerce")
    p = pd.to_numeric(frame["calibrated_probability"], errors="coerce")
    valid = y.notna() & p.notna()
    yv = y[valid].astype(int).to_numpy()
    pv = p[valid].astype(float).to_numpy()
    if len(yv) == 0:
        return None
    result: dict[str, float | int] = {
        "rows": int(len(yv)),
        "positive_rate": float(np.mean(yv)),
        "average_precision": float(average_precision_score(yv, pv)) if np.any(yv == 1) else 0.0,
        "brier_score": float(brier_score_loss(yv, pv)),
        "roc_auc": float(roc_auc_score(yv, pv)) if len(np.unique(yv)) > 1 else 0.0,
    }
    result.update(ranking_metrics(yv, pv, 0.10))
    return result


def _performance_windows(predictions: pd.DataFrame) -> dict[str, Any]:
    if predictions.empty or "snapshot_month" not in predictions:
        return {"available": False, "reason": "prediction artifact missing or empty"}
    unique_months = _month_strings(predictions["snapshot_month"])
    if len(unique_months) < 4:
        return {"available": False, "reason": "need at least four prediction months"}
    current_months = unique_months[-2:]
    reference_months = unique_months[-4:-2]
    month_text = pd.to_datetime(predictions["snapshot_month"], errors="coerce").dt.strftime("%Y-%m")
    reference = predictions[month_text.isin(reference_months)].copy()
    current = predictions[month_text.isin(current_months)].copy()
    ref_metrics = _performance(reference)
    cur_metrics = _performance(current)
    if not ref_metrics or not cur_metrics:
        return {"available": False, "reason": "insufficient labelled prediction rows"}
    delta = {
        metric: _safe_float(float(cur_metrics[metric]) - float(ref_metrics[metric]))
        for metric in ("average_precision", "brier_score", "roc_auc", "recall_at_top_10pct")
    }
    return {
        "available": True,
        "reference_period": f"{reference_months[0]}..{reference_months[-1]}",
        "current_period": f"{current_months[0]}..{current_months[-1]}",
        "reference": ref_metrics,
        "current": cur_metrics,
        "delta": delta,
    }


def _load_aggregate_frame(settings: Settings) -> pd.DataFrame:
    import psycopg
    with psycopg.connect(settings.postgres_dsn) as conn:
        return pd.read_sql_query(
            "SELECT * FROM features.department_monthly_fusion ORDER BY report_month",
            conn,
        )


def _evidently_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    columns: list[str],
    drift_share_threshold: float,
    output_dir: Path,
) -> tuple[dict[str, Any], Path, Path, list[str]]:
    # Lazy import keeps non-MLOps commands usable without the optional Evidently package.
    from evidently import DataDefinition, Dataset, Report
    from evidently.metrics import DriftedColumnsCount
    from evidently.presets import DataDriftPreset

    reference_view = reference[columns].replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
    current_view = current[list(reference_view.columns)].replace([np.inf, -np.inf], np.nan)
    usable = [
        column
        for column in reference_view.columns
        if reference_view[column].notna().any() and current_view[column].notna().any()
    ]
    if not usable:
        raise ValueError("No non-empty columns are available for Evidently drift evaluation")
    reference_view = reference_view[usable]
    current_view = current_view[usable]
    numerical = [column for column in usable if pd.api.types.is_numeric_dtype(reference_view[column])]
    categorical = [column for column in usable if column not in numerical]
    definition = DataDefinition(numerical_columns=numerical, categorical_columns=categorical)
    ref_ds = Dataset.from_pandas(reference_view, data_definition=definition)
    cur_ds = Dataset.from_pandas(current_view, data_definition=definition)
    report = Report([
        DataDriftPreset(drift_share=drift_share_threshold),
        DriftedColumnsCount(),
    ])
    snapshot = report.run(current_data=cur_ds, reference_data=ref_ds)
    payload = snapshot.dict()
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "evidently_data_drift.html"
    json_path = output_dir / "evidently_data_drift.json"
    snapshot.save_html(str(html_path))
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return payload, html_path, json_path, usable


def run_monitoring_cycle(settings: Settings, *, scope: str | None = None) -> dict[str, Any]:
    scope = scope or settings.mlops_monitoring_scope
    settings.validate_mlops_runtime(scope=scope)
    generated = datetime.now(timezone.utc)
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    artifact_root = Path(settings.mlops_monitoring_artifact_root)
    run_dir = artifact_root / stamp

    if scope == "synthetic_demo":
        panel_path = Path(settings.mlops_synthetic_panel_path)
        if not panel_path.exists():
            raise FileNotFoundError(
                f"Synthetic STEP 6 panel not found: {panel_path}. Run STEP 6 generation first."
            )
        frame = pd.read_csv(panel_path)
        columns = [column for column in feature_columns(settings.mlops_feature_set) if column in frame]
        windows = select_recent_month_windows(
            frame,
            month_column="snapshot_month",
            reference_months=settings.mlops_reference_months,
            current_months=settings.mlops_current_months,
        )
        predictions_path = Path(settings.mlops_predictions_path)
        predictions = pd.read_csv(predictions_path) if predictions_path.exists() else pd.DataFrame()
        model_performance = _performance_windows(predictions)
    elif scope == "aggregate":
        frame = _load_aggregate_frame(settings)
        ignored = {
            "department_id_hash", "report_month", "created_at", "updated_at",
            "has_activity_data", "has_slack_data",
        }
        columns = [
            column for column in frame.columns
            if column not in ignored and pd.api.types.is_numeric_dtype(frame[column])
        ]
        windows = select_recent_month_windows(
            frame,
            month_column="report_month",
            reference_months=settings.mlops_reference_months,
            current_months=settings.mlops_current_months,
        )
        model_performance = {
            "available": False,
            "reason": "employee-level model-performance monitoring is intentionally disabled for aggregate production data",
        }
    else:
        raise ValueError("scope must be aggregate or synthetic_demo")

    payload, html_path, json_path, monitored_columns = _evidently_report(
        windows.reference,
        windows.current,
        columns=columns,
        drift_share_threshold=settings.mlops_drift_share_threshold,
        output_dir=run_dir,
    )
    drifted_count, drift_share = extract_drift_count(payload)
    total_features = len(monitored_columns)
    if drifted_count is None and drift_share is not None:
        drifted_count = int(round(drift_share * total_features))
    dataset_drift = bool(drift_share is not None and drift_share >= settings.mlops_drift_share_threshold)
    summary = {
        "status": "ok",
        "generated_at": generated.isoformat(),
        "scope": scope,
        "privacy_contract": (
            "synthetic employee-level monitoring only" if scope == "synthetic_demo"
            else "department/cohort aggregate monitoring only"
        ),
        "feature_set": settings.mlops_feature_set if scope == "synthetic_demo" else "department_monthly_fusion",
        "data_drift": {
            "reference_period": windows.reference_period,
            "current_period": windows.current_period,
            "reference_rows": int(len(windows.reference)),
            "current_rows": int(len(windows.current)),
            "monitored_features": total_features,
            "drifted_features": drifted_count,
            "drift_share": drift_share,
            "threshold": settings.mlops_drift_share_threshold,
            "dataset_drift": dataset_drift,
            "evidently_html": str(html_path),
            "evidently_json": str(json_path),
        },
        "model_performance": model_performance,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_root.mkdir(parents=True, exist_ok=True)
    latest_summary = artifact_root / "latest_summary.json"
    latest_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(html_path, artifact_root / "latest_evidently_data_drift.html")
    shutil.copyfile(json_path, artifact_root / "latest_evidently_data_drift.json")
    return summary
