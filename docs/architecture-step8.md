# STEP 8 — MLOps / drift monitoring architecture

```text
STEP 3 NLP benchmark ───────┐
                            ├──> MLflow Tracking (PostgreSQL metadata)
STEP 6 synthetic ML runs ───┘            │
                                         └── local artifact volume

Feature batches / synthetic panel
              │
              ▼
        Evidently 0.7
  DataDriftPreset + DriftedColumnsCount
              │
       ┌──────┴────────┐
       ▼               ▼
 HTML/JSON report   latest_summary.json
       │               │
       │               └──> FastAPI /metrics
       │                          │
       └──> MLflow run            ▼
                              Prometheus
                                  │
                                  ▼
                                Grafana
```

## Privacy boundary

- `aggregate`: only `features.department_monthly_fusion` is evaluated. No employee model quality or employee risk is monitored.
- `synthetic_demo`: STEP 6 generated employee panel and test predictions may be used for model-performance monitoring.
- Prometheus labels never contain employee, department, Slack, or HMAC identifiers.
- Evidently summary artifacts contain feature-level statistics only; raw Slack message text is never part of STEP 8.
