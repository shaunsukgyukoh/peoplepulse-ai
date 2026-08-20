from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str) -> Path:
    candidate = ROOT / path
    if not candidate.exists():
        raise SystemExit(f"[ERROR] missing STEP 8 file: {path}")
    return candidate


def main() -> int:
    compose = require("docker-compose.yml").read_text(encoding="utf-8")
    pyproject = require("pyproject.toml").read_text(encoding="utf-8")
    mlflow_bootstrap = require("infra/mlflow/start_mlflow.py").read_text(encoding="utf-8")
    mlflow_dockerfile = require("Dockerfile.mlflow").read_text(encoding="utf-8")
    prometheus_metrics = require("src/peoplepulse/monitoring/prometheus.py").read_text(encoding="utf-8")
    datasource = require("infra/grafana/provisioning/datasources/prometheus.yml").read_text(encoding="utf-8")

    for path in (
        "Dockerfile.mlflow",
        "Dockerfile.monitoring",
        "infra/prometheus/prometheus.yml",
        "infra/prometheus/alerts.yml",
        "infra/grafana/provisioning/datasources/prometheus.yml",
        "infra/grafana/provisioning/dashboards/peoplepulse.yml",
        "infra/grafana/dashboards/peoplepulse-mlops.json",
        "src/peoplepulse/monitoring/drift.py",
        "src/peoplepulse/monitoring/prometheus.py",
        "src/peoplepulse/api/monitoring.py",
    ):
        require(path)

    for service in ("mlflow:", "prometheus:", "grafana:", "monitoring-worker:"):
        if service not in compose:
            raise SystemExit(f"[ERROR] docker-compose missing {service}")

    for expected in (
        "prom/prometheus:v3.13.2",
        "grafana/grafana:13.1.0",
    ):
        if expected not in compose:
            raise SystemExit(f"[ERROR] docker-compose missing pinned image {expected}")

    if "prometheus-flask-exporter==0.23.2" not in mlflow_dockerfile:
        raise SystemExit("[ERROR] Dockerfile.mlflow missing prometheus-flask-exporter required by --expose-prometheus")

    if "import mlflow, prometheus_flask_exporter" not in mlflow_dockerfile:
        raise SystemExit("[ERROR] Dockerfile.mlflow missing build-time Prometheus exporter import check")

    for version in ("mlflow==3.15.1", "evidently==0.7.21"):
        if version not in pyproject:
            raise SystemExit(f"[ERROR] pyproject missing {version}")

    for flag in ("mlflow", "db", "upgrade", "--allowed-hosts", "--cors-allowed-origins", "--expose-prometheus"):
        if flag not in mlflow_bootstrap:
            raise SystemExit(f"[ERROR] MLflow bootstrap missing security/metrics flag {flag}")

    forbidden_metric_labels = ("employee_id_hash", "department_id_hash", "slack_user_id", "canonical_employee")
    for token in forbidden_metric_labels:
        if token in prometheus_metrics:
            raise SystemExit(f"[ERROR] identifying Prometheus label/token detected: {token}")

    if "http://prometheus:9090" not in datasource:
        raise SystemExit("[ERROR] Grafana Prometheus datasource must use the internal Docker DNS name")

    dashboard = json.loads(
        require("infra/grafana/dashboards/peoplepulse-mlops.json").read_text(encoding="utf-8")
    )
    if dashboard.get("uid") != "peoplepulse-mlops":
        raise SystemExit("[ERROR] Grafana dashboard UID mismatch")

    print("[OK] STEP 8 static preflight")
    print("  mlflow=3.15.1")
    print("  evidently=0.7.21")
    print("  prometheus=3.13.2-lts")
    print("  grafana=13.1.0")
    print("  mlflow_bootstrap=create-db -> db-upgrade -> server")
    print("  mlflow_prometheus_exporter=prometheus-flask-exporter==0.23.2")
    print("  mlflow_workers=1 default for deterministic local startup")
    print("  mlflow_health=http://127.0.0.1:5000/health")
    print("  mlflow_security=allowed-hosts + cors (middleware enabled)")
    print("  prometheus_labels=no employee/department/slack identifiers")
    print("  privacy=aggregate-production / synthetic-demo-model-monitoring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
