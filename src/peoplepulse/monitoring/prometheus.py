from __future__ import annotations

import json
import time
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram

API_REQUESTS = Counter(
    "peoplepulse_api_requests_total",
    "PeoplePulse FastAPI HTTP requests",
    ["method", "route", "status"],
)
API_LATENCY = Histogram(
    "peoplepulse_api_request_duration_seconds",
    "PeoplePulse FastAPI request latency",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
MONITORING_SUCCESS = Gauge(
    "peoplepulse_monitoring_run_success",
    "1 when the latest monitoring cycle succeeded",
)
MONITORING_TIMESTAMP = Gauge(
    "peoplepulse_monitoring_last_success_timestamp_seconds",
    "Unix timestamp of the latest successful monitoring cycle",
)
DRIFT_SHARE = Gauge("peoplepulse_data_drift_share", "Share of monitored features with detected drift", ["scope"])
DRIFTED_FEATURES = Gauge("peoplepulse_data_drifted_features", "Number of drifted features", ["scope"])
MONITORED_FEATURES = Gauge("peoplepulse_data_monitored_features", "Number of monitored features", ["scope"])
MODEL_METRIC = Gauge(
    "peoplepulse_model_monitoring_metric",
    "Synthetic-demo model monitoring metric",
    ["metric", "window"],
)


def observe_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    API_REQUESTS.labels(method=method, route=route, status=str(status)).inc()
    API_LATENCY.labels(method=method, route=route).observe(duration_seconds)


def refresh_monitoring_gauges(summary_path: str | Path) -> None:
    path = Path(summary_path)
    if not path.exists():
        MONITORING_SUCCESS.set(0)
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        MONITORING_SUCCESS.set(0)
        return
    if payload.get("status") != "ok":
        MONITORING_SUCCESS.set(0)
        return
    MONITORING_SUCCESS.set(1)
    generated = payload.get("generated_at")
    try:
        from datetime import datetime
        MONITORING_TIMESTAMP.set(datetime.fromisoformat(str(generated).replace("Z", "+00:00")).timestamp())
    except Exception:
        MONITORING_TIMESTAMP.set(time.time())
    scope = str(payload.get("scope", "unknown"))
    drift = payload.get("data_drift", {})
    for gauge, key in (
        (DRIFT_SHARE, "drift_share"),
        (DRIFTED_FEATURES, "drifted_features"),
        (MONITORED_FEATURES, "monitored_features"),
    ):
        value = drift.get(key)
        if value is not None:
            gauge.labels(scope=scope).set(float(value))
    perf = payload.get("model_performance", {})
    if perf.get("available"):
        for window in ("reference", "current"):
            for metric in ("average_precision", "brier_score", "roc_auc", "recall_at_top_10pct"):
                value = perf.get(window, {}).get(metric)
                if value is not None:
                    MODEL_METRIC.labels(metric=metric, window=window).set(float(value))
