# STEP 7 Runbook

## 1. Static preflight

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/check_step7_dashboard.py
```

## 2. Build the dashboard stack

```powershell
.\scripts\run_step7_dashboard.ps1
```

Open:

```text
http://localhost:3000
```

API:

```text
http://localhost:8000/health
http://localhost:8000/docs
```

## 3. Real-time Slack panel

Keep the verified host CUDA worker running:

```powershell
.\scripts\run_nlp_worker_local.ps1
```

In another terminal start the Slack listener:

```powershell
docker compose --profile slack up -d slack-listener
```

Send a demo message in `#peoplepulse-test`. The flow is:

```text
Slack -> Socket Mode -> Redis Stream -> host CUDA KLUE RoBERTa
      -> PostgreSQL derived probabilities -> FastAPI SSE -> dashboard
```

The browser does not receive the raw message.

## 4. Monthly report upload

Use the dashboard's `Monthly Report Upload` section. Provide:

- `report_month`,
- current `ACTIVITY_ADMIN_TOKEN`,
- all three `.xls/.xlsx` reports.

The existing STEP 4 API still performs header-based report type detection, forward-fill, Pandera validation, privacy filtering and PostgreSQL persistence.

## 5. Synthetic retention evaluation

The dashboard checks runtime STEP 6 artifacts first:

```text
artifacts/ml/step6/
```

If they exist, they are shown. If not, the repository reference metrics are used. Run STEP 6 again to refresh local metrics and SHAP:

```powershell
.\scripts\run_step6_experiment.ps1
```

## 6. SHAP

Runtime path:

```text
artifacts/ml/step6/privacy_safe/shap/shap_feature_importance.csv
```

When the file exists, the dashboard renders actual mean absolute SHAP magnitudes. Without it, the checked-in reference rank is displayed without invented magnitudes.

## 7. Stop

```powershell
docker compose --profile dashboard down
```
