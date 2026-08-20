# STEP 8 runbook

## Start

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/check_step8_mlops.py
.\scripts\run_step8_mlops.ps1 -Scope synthetic_demo
```

For real cohort data use:

```powershell
.\scripts\run_step8_mlops.ps1 -Scope aggregate
```

The aggregate path only reads `features.department_monthly_fusion` and does not calculate employee model performance.

## URLs

- MLflow: `http://localhost:5000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- FastAPI Prometheus metrics: `http://localhost:8000/metrics`
- Monitoring summary: `http://localhost:8000/api/v1/monitoring/summary`
- Latest Evidently HTML: `http://localhost:8000/api/v1/monitoring/evidently/latest`

## Grafana

Default credentials come from `.env` (`GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`). Change the default password before sharing the stack on a network.

The `PeoplePulse MLOps & Drift Monitoring` dashboard is provisioned automatically.

## One-off monitoring

```powershell
docker compose --profile mlops run --rm -e MLOPS_MONITORING_SCOPE=synthetic_demo monitoring-worker `
  python scripts/run_step8_drift.py --scope synthetic_demo
```

## Troubleshooting

```powershell
docker compose --profile mlops ps
docker compose --profile mlops logs --tail=100 mlflow
docker compose --profile mlops logs --tail=100 monitoring-worker
docker compose --profile mlops logs --tail=100 prometheus
docker compose --profile mlops logs --tail=100 grafana
```

If the synthetic panel is missing, run STEP 6 dataset generation first. If predictions are absent, data drift still runs but model-performance monitoring is reported as unavailable.
