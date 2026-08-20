# Apply STEP 2 patch

Copy the contents of this directory over the existing `peoplepulse-ai` STEP 1 repository, preserving the directory structure.

Important: do not overwrite your real `.env` with `.env.example`. Add the new Slack/queue variables from `.env.example` to your existing `.env` manually.

# Apply PeoplePulse AI STEP 3 patch

1. Back up your existing `.env`; this patch does not contain a real `.env`.
2. Extract this patch over the existing `peoplepulse-ai` project and allow file overwrite.
3. Copy the STEP 3 NLP variables from `.env.example` into your existing `.env`.
4. Apply `infra/postgres/migrations/002_step3_nlp.sql` to the existing PostgreSQL volume.
5. Install `.[nlp,dev]`, train the baseline, then fine-tune/compare Transformer candidates.
6. Copy the selected Transformer checkpoint to `artifacts/models/selected` with `scripts/select_nlp_model.py`.
7. Start `docker compose --profile slack --profile nlp up -d --build`.

See the updated `README.md` for exact PowerShell commands.


# STEP 3.1 Patch

Copy/merge this patch into the existing `peoplepulse-ai` project root.

This patch:
- records the Windows/NVIDIA CUDA 12.1 PyTorch install path,
- prevents the NLP extra from replacing the manually installed CUDA PyTorch wheel,
- adds validation-only per-label threshold tuning,
- fixes CUDA latency measurement with explicit synchronization,
- adds calibrated checkpoint evaluators,
- adds a one-command PowerShell evaluation runner,
- records the first local experiment result and its limitations.

After merging:

```powershell
python scripts/check_cuda.py
.\scripts\run_step3_1_eval.ps1
```

# PeoplePulse AI STEP 3.2 Patch

Merge this patch into the existing STEP 3.1 project root.

## What this patch does

- Promotes the best measured Transformer under explicit Macro-F1/latency gates.
- Loads validation-tuned per-label thresholds at runtime.
- Stores active labels, thresholds and inference device in PostgreSQL.
- Adds a synthetic end-to-end smoke test: Redis -> CUDA Transformer -> PostgreSQL.
- Keeps the verified Windows host CUDA path for STEP 3.2; the Docker NLP image remains CPU-portable.

## Run

```powershell
python scripts/promote_nlp_model.py

Get-Content -Raw infra/postgres/migrations/003_step3_runtime_thresholds.sql |
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

docker compose up -d postgres redis
.\scripts\run_nlp_worker_local.ps1
```

Open a second PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/smoke_test_realtime_nlp.py
```

After the smoke test passes, start the Slack listener and test a synthetic/demo message in `#peoplepulse-test`.

# PeoplePulse AI STEP 3.2.1 Redis timeout fix

Merge this patch into the existing STEP 3.2 project root.

The issue:
- redis-py 8.x uses a finite socket read timeout.
- The NLP worker uses `XREADGROUP BLOCK=5000ms`.
- A 5-second socket timeout can race the 5-second Redis blocking window and terminate the worker.

The fix:
- `NLP_REDIS_SOCKET_TIMEOUT_SECONDS=15`
- validation requires socket timeout > XREADGROUP block duration
- transient Redis `TimeoutError` no longer terminates the long-running worker

Run:

```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\run_nlp_worker_local.ps1
```

Then in a second PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/smoke_test_realtime_nlp.py
```

# PeoplePulse AI STEP 4 Patch

Merge this patch into the existing STEP 3.2.1 project root. Do not replace your real `.env` file.

Then follow `docs/step4-runbook.md`.

Core checks performed before packaging:
- Python source compile succeeded.
- 21 dependency-light regression/unit tests passed.
- Synthetic `.xlsx` workbook was created and inspected with the spreadsheet artifact tool.
- Full Pandera/calamine/PostgreSQL integration is intended to run in the user's Python 3.11 environment after `pip install -e ".[activity,dev]"`.

# PeoplePulse AI STEP 4.1 — Actual 3-report schema patch

Merge this patch into your existing project root.

## 1. Remove STEP 4.0 legacy files

```powershell
.\scripts\cleanup_step4_legacy.ps1
```

## 2. Install/update STEP 4 dependencies

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[activity,dev]"
```

This activity extra does not reinstall PyTorch.

## 3. Update `.env`

For actual employee reports (safe default):

```env
ACTIVITY_CONTENT_POLICY_PATH=configs/activity_content_policy.json
ACTIVITY_PRIVACY_MODE=aggregate
ACTIVITY_MIN_COHORT_SIZE=5
ACTIVITY_DEMO_FILENAME_PREFIX=Synthetic_
ACTIVITY_MAX_UPLOAD_BYTES=20971520
ACTIVITY_WORKDAY_START_HOUR=9
ACTIVITY_WORKDAY_END_HOUR=18
ACTIVITY_ADMIN_TOKEN=<your-existing-admin-secret>
```

For the included synthetic 3-file portfolio test only:

```env
APP_ENV=development
ACTIVITY_PRIVACY_MODE=synthetic_demo
```

`synthetic_demo` is blocked when `APP_ENV=production` and also requires every uploaded filename to start with `Synthetic_`.

## 4. Apply the new migration

```powershell
docker compose up -d postgres redis
python scripts/apply_step4_actual_reports_migration.py
```

## 5. Rebuild/recreate the API

```powershell
docker compose --profile activity up -d --build --force-recreate api
docker compose --profile activity ps
```

Verify the PORTS column contains:

```text
0.0.0.0:8000->8000/tcp
```

Then:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## 6. Upload all 3 reports at once

Open:

```text
http://localhost:8000/admin/activity-upload
```

The backend auto-detects report type from headers. Upload order does not matter.

Synthetic test files are under:

```text
data/synthetic/activity/actual-format/
```

Report month:

```text
2026-07
```

## 7. Verify

```powershell
python scripts/check_activity_features.py
```

In `aggregate` mode, real data is written only to:

```text
features.department_monthly_activity
```

In `synthetic_demo` mode, employee-level portfolio data is written only to:

```text
features.synthetic_employee_monthly_activity
```

# PeoplePulse AI STEP 5 Patch

Merge this patch into the existing STEP 4.1 project root.

## What STEP 5 adds

- explicit identity resolution instead of fuzzy name matching
- HMAC-only Slack-user -> department map for production aggregate mode
- HMAC-only canonical identity map for synthetic portfolio mode
- Slack 7/30/90-day rolling features
- employee-first -> department averaging for production cohort signals
- department monthly Slack/activity fusion table
- synthetic employee-level ML-ready feature table
- STEP 6 feature-matrix CSV + JSON manifest exporter

## 1. Keep the same HMAC key

Do **not** change `EMPLOYEE_HASH_KEY`. STEP 5 joins identifiers produced by STEP 2/3 and STEP 4.

## 2. Apply migration

```powershell
.\.venv\Scripts\Activate.ps1
docker compose up -d postgres redis
python scripts/apply_step5_migration.py
```

## 3A. Synthetic portfolio path

Use only with:

```env
APP_ENV=development
ACTIVITY_PRIVACY_MODE=synthetic_demo
```

Prerequisite: STEP 4.1 synthetic 3-report upload for `2026-07` has populated
`features.synthetic_employee_monthly_activity`.

Then:

```powershell
python scripts/load_identity_map.py `
  --mode synthetic_demo `
  --path "data/synthetic/identity/canonical_employee_map.csv"

python scripts/seed_step5_synthetic_slack.py
python scripts/build_step5_features.py --month 2026-07 --mode synthetic_demo
python scripts/check_step5_features.py --month 2026-07 --mode synthetic_demo
python scripts/export_step5_feature_matrix.py --month 2026-07 --mode synthetic_demo
```

Or run the first four commands with:

```powershell
.\scripts\run_step5_synthetic_demo.ps1
```

Expected final table:

```text
features.synthetic_employee_retention_feature
```

Generated STEP 6 inputs:

```text
artifacts/features/step5_synthetic_demo_2026-07.csv
artifacts/features/step5_synthetic_demo_2026-07_manifest.json
```

Identifiers are traceability columns only and are excluded from `model_feature_columns` in the manifest.

## 3B. Production-safe aggregate path

Create a local CSV outside Git using the template in
`data/synthetic/identity/slack_department_map_template.csv`:

```csv
slack_user_id,department
U01234567,연구개발본부
U07654321,연구개발본부
```

Then:

```powershell
python scripts/load_identity_map.py --mode aggregate --path "C:\secure\slack_department_map.csv"
python scripts/build_step5_features.py --month 2026-07 --mode aggregate
python scripts/check_step5_features.py --month 2026-07 --mode aggregate
```

Production output is cohort-level only:

```text
features.department_monthly_slack_signal
features.department_monthly_fusion
```

Raw Slack IDs, names and department text are not persisted by the identity loader. Departments below
`ACTIVITY_MIN_COHORT_SIZE` are excluded from the Slack/fused feature tables.

# PeoplePulse AI STEP 6 Patch

Merge this patch into the existing STEP 5 project root.

## Install

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[ml,dev]"
```

STEP 6 does not reinstall PyTorch, so the verified CUDA 12.1 NLP environment is left intact.

## Optional DB migration

```powershell
docker compose up -d postgres
python scripts/apply_step6_migration.py
```

The database tables enforce `data_scope = synthetic_demo`.

## Run

```powershell
.\scripts\run_step6_experiment.ps1
```

This generates a synthetic 36-month panel, runs Logistic Regression / XGBoost / LightGBM / CatBoost,
selects on validation Average Precision, calibrates on the disjoint validation window, evaluates on the
untouched temporal test window, compares privacy-safe vs synthetic-full features, and creates SHAP output.

## Verify

```powershell
python scripts/check_step6_results.py
```

See:
- `docs/architecture-step6.md`
- `docs/step6-runbook.md`
- `docs/model-card-step6.md`
- `docs/step6-reference-results.md`

## Suggested Git commit

```text
feat(step6): add synthetic attrition ML evaluation pipeline
```

Body:

```text
- add purged temporal split for 90-day attrition targets
- compare logistic regression, XGBoost, LightGBM, and CatBoost
- add PR-AUC, Recall@Top-K, calibration, and SHAP evaluation
- add privacy-safe feature set and intent-proxy ablation
- enforce synthetic-only employee-level model training
```

# PeoplePulse AI STEP 6.1 — dependency preflight + fail-fast runner

Merge this patch into the existing STEP 6 project root.

## Why

The STEP 6 project already declares `catboost` and `matplotlib` inside the `ml` optional dependency group. The local `.venv` was missing those packages, so model training and SHAP plotting failed. The old PowerShell runner also continued after native Python commands returned non-zero exit codes and incorrectly printed a final success message.

## Apply and run

```powershell
cd "C:\Users\a\Documents\Agentic-AI project\peoplepulse-ai"
.\.venv\Scripts\Activate.ps1

python -m pip install -e ".[ml,dev]"
python scripts/check_step6_dependencies.py
.\scripts\run_step6_experiment.ps1
```

The runner now checks dependencies before generating data and explicitly checks `$LASTEXITCODE` after every Python command. It stops immediately on failure and prints `[OK] STEP 6 experiment complete` only when every stage succeeds.

# PeoplePulse AI STEP 6.2 — Python 3.11 / XGBoost compatibility fix

Merge this patch into the existing project root.

## Why this is needed

XGBoost 3.3+ requires Python 3.12+.
This project currently runs on Python 3.11, so the ML extra must resolve to XGBoost 3.2.x.

The dependency is now selected by Python version:

```toml
"xgboost>=3.2,<3.3; python_version < '3.12'",
"xgboost>=3.3,<4; python_version >= '3.12'",
```

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -e ".[ml,dev]"
python scripts/check_step6_dependencies.py
.\scripts\run_step6_experiment.ps1
```

Expected on Python 3.11:

```text
xgboost=3.2.0
```

# PeoplePulse AI STEP 7 Patch

Merge the STEP 7 patch into the existing repository root.

## 1. Keep the existing `.env`

Do not replace your real `.env`. Add the STEP 7 variables from `.env.example` only if needed.

## 2. Preflight

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/check_step7_dashboard.py
```

## 3. Build and start

```powershell
.\scripts\run_step7_dashboard.ps1
```

Open:

```text
http://localhost:3000
```

The API must show:

```text
http://localhost:8000/health
```

## 4. Live Slack

Keep the verified Windows CUDA worker running:

```powershell
.\scripts\run_nlp_worker_local.ps1
```

Start the listener:

```powershell
docker compose --profile slack up -d slack-listener
```

## 5. Refresh STEP 6 metrics / SHAP when desired

```powershell
.\scripts\run_step6_experiment.ps1
```

The dashboard automatically prefers local generated artifacts and falls back to checked-in reference metrics when they are absent.

## 6. Git commit

```powershell
git add .
git commit -m "feat(step7): add real-time PeoplePulse analytics dashboard" `
  -m "Add Next.js 16.3 dashboard with Executive, Slack SSE, report upload, ML evaluation, SHAP, and performance views." `
  -m "Add FastAPI dashboard read endpoints and server-sent events over derived privacy-aware signals." `
  -m "Keep production analytics cohort-scoped and employee-level attrition evaluation synthetic-only."
```

# PeoplePulse AI STEP 7.1 — Dashboard Docker public-directory fix

Merge this patch into the project root.

## Cause

The Next.js build succeeded, but the runner stage failed on:

```dockerfile
COPY --from=builder /app/public ./public
```

because the dashboard did not yet contain a `public/` directory.

## Fix

- Add `dashboard/public/.gitkeep`.
- Ensure the builder creates `public/` before `next build`.
- Copy it with the same non-root ownership as the standalone output.
- Pre-apply Next.js 16's `.next/dev/types/**/*.ts` tsconfig include.

## Verify

```powershell
python scripts/check_step7_dashboard_docker.py

docker compose --profile dashboard build --no-cache dashboard

docker compose --profile dashboard up -d api dashboard

docker compose --profile dashboard ps
```

Expected dashboard port:

```text
0.0.0.0:3000->3000/tcp
```

Then open:

```text
http://localhost:3000
```


# PeoplePulse AI STEP 8 — MLOps / drift monitoring

Merge this patch into the existing `peoplepulse-ai` project root. The patch also carries the STEP 7.1 Next.js `public/` Docker fix so it can be applied safely on top of the latest project state.

## 1. Keep existing secrets

Do **not** replace your real `.env` with `.env.example`. Keep the existing `EMPLOYEE_HASH_KEY`, Slack tokens, PostgreSQL password, and activity admin token.

Add or review these STEP 8 values in `.env`:

```env
MLFLOW_PORT=5000
MLFLOW_POSTGRES_DB=peoplepulse_mlflow
MLFLOW_WORKERS=2
MLFLOW_SERVER_ALLOWED_HOSTS=localhost:*,127.0.0.1:*,mlflow:5000,peoplepulse-mlflow:5000
MLFLOW_SERVER_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000,http://127.0.0.1:5000
MLFLOW_MONITORING_EXPERIMENT=PeoplePulse-Monitoring-Step8

MLOPS_MONITORING_SCOPE=synthetic_demo
MLOPS_MONITORING_INTERVAL_SECONDS=3600
MLOPS_REFERENCE_MONTHS=6
MLOPS_CURRENT_MONTHS=3
MLOPS_DRIFT_SHARE_THRESHOLD=0.30
MLOPS_FEATURE_SET=privacy_safe

PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION=15d
GRAFANA_PORT=3001
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<change-this-local-password>
```

`synthetic_demo` is blocked when `APP_ENV=production`.

## 2. Static preflight

```powershell
cd "C:\Users\a\Documents\Agentic-AI project\peoplepulse-ai"
.\.venv\Scripts\Activate.ps1
python scripts/check_step8_mlops.py
```

Expected:

```text
[OK] STEP 8 static preflight
  mlflow=3.15.1
  evidently=0.7.21
  prometheus=3.13.2-lts
  grafana=13.1.0
  mlflow_security=allowed-hosts + cors (middleware enabled)
  prometheus_labels=no employee/department/slack identifiers
```

## 3. Synthetic demo prerequisites

For the full synthetic demo, STEP 6 should already have generated:

```text
data/synthetic/ml/step6_attrition_panel.csv
```

If it is missing:

```powershell
python scripts/generate_step6_synthetic_panel.py
```

If `artifacts/ml/step6/privacy_safe/test_predictions.csv` is missing, STEP 8 still creates data-drift reports; model-performance monitoring is shown as unavailable until STEP 6 training finishes successfully.

## 4. Start STEP 8

```powershell
.\scripts\run_step8_mlops.ps1 -Scope synthetic_demo
```

The script performs fail-fast static validation, builds/starts the services, imports available STEP 3/6 history into MLflow, generates the initial Evidently snapshot, and starts the recurring monitoring worker.

## 5. Verify services

```powershell
docker compose --profile mlops ps
```

Expected services include:

```text
peoplepulse-postgres
peoplepulse-api
peoplepulse-mlflow
peoplepulse-monitoring-worker
peoplepulse-prometheus
peoplepulse-grafana
```

Open:

```text
http://localhost:5000                         MLflow
http://localhost:9090                         Prometheus
http://localhost:3001                         Grafana
http://localhost:8000/metrics                 FastAPI Prometheus metrics
http://localhost:8000/api/v1/monitoring/summary
http://localhost:8000/api/v1/monitoring/evidently/latest
```

## 6. Production-safe aggregate mode

```powershell
.\scripts\run_step8_mlops.ps1 -Scope aggregate
```

This path reads only `features.department_monthly_fusion`. It does not perform employee-level model-performance monitoring. The default 6-month reference + 3-month current window needs at least 9 distinct months of aggregate history; until that history exists, use the synthetic demo for portfolio validation or reduce the window settings deliberately for a smoke test.

## 7. Logs

```powershell
docker compose --profile mlops logs --tail=100 mlflow
docker compose --profile mlops logs --tail=100 monitoring-worker
docker compose --profile mlops logs --tail=100 prometheus
docker compose --profile mlops logs --tail=100 grafana
```

## Privacy contract

- Real/production: department/cohort drift only.
- Synthetic demo: employee-level model monitoring allowed only on generated data.
- Prometheus labels contain no employee, department, Slack, canonical employee, or HMAC identifiers.
- Raw Slack message text is never included in STEP 8 monitoring artifacts.

# PeoplePulse AI STEP 8.1 — MLflow startup fix

This patch fixes an MLflow container that builds successfully but remains unhealthy
during the first PostgreSQL-backed startup.

## Changes

- Bootstrap the dedicated `peoplepulse_mlflow` database.
- Run `mlflow db upgrade <backend-uri>` exactly once before starting the server.
- Default local MLflow workers from 2 -> 1 to avoid first-start migration races.
- Explicitly enable artifact serving and `mlflow-artifacts:/` as the default root.
- Probe `127.0.0.1:5000/health` instead of `localhost`.
- Increase the first-start healthcheck grace period.
- Print MLflow logs automatically if STEP 8 infrastructure startup fails.
- Add `scripts/diagnose_step8_mlflow.ps1`.

## Apply

Merge this patch into the project root. Keep the user's existing `.env`; do not
replace it with `.env.example`.

For local development, set:

```env
MLFLOW_WORKERS=1
```

Then:

```powershell
docker compose --profile mlops rm -sf mlflow
docker compose --profile mlops build --no-cache mlflow
docker compose --profile mlops up -d postgres
docker compose --profile mlops up -d mlflow
docker compose --profile mlops ps -a
docker compose --profile mlops logs --tail=200 mlflow
```

Expected log sequence:

```text
[MLflow bootstrap] database=peoplepulse_mlflow already exists
[MLflow bootstrap] applying MLflow DB migrations
...
[MLflow bootstrap] DB migrations complete
[MLflow bootstrap] starting tracking server workers=1 ...
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:5000
```

Health:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:5000/health
```

Expected body:

```text
OK
```

Then run the full stack:

```powershell
.\scripts\run_step8_mlops.ps1 -Scope synthetic_demo
```

If it still fails:

```powershell
.\scripts\diagnose_step8_mlflow.ps1
```

# PeoplePulse AI STEP 8.2 — MLflow Prometheus Exporter Dependency Fix

The MLflow database bootstrap is already succeeding. The current crash is caused by
`--expose-prometheus` importing `prometheus_flask_exporter`, which is an optional MLflow dependency.

This patch:
- installs `prometheus-flask-exporter==0.23.2` in `Dockerfile.mlflow`
- performs a build-time import check so the image fails early if the exporter is absent
- keeps STEP 8.1 DB migration/bootstrap and `127.0.0.1` healthcheck hardening
- keeps the default local MLflow worker count at 1
- adds `scripts/verify_step8_mlflow_image.ps1`
- strengthens STEP 8 preflight

## Important `.env` note

Do NOT overwrite your real `.env`.

If your `.env` still contains:

```env
MLFLOW_WORKERS=2
```

change it to:

```env
MLFLOW_WORKERS=1
```

for the local portfolio stack. `docker-compose.yml` defaults to 1, but `.env` overrides that default.

## Apply and verify

```powershell
.\.venv\Scripts\Activate.ps1

python scripts/check_step8_mlops.py

.\scripts\verify_step8_mlflow_image.ps1

docker compose --profile mlops rm -sf mlflow

docker compose --profile mlops up -d mlflow

docker compose --profile mlops ps -a

docker compose --profile mlops logs --tail=120 mlflow

Invoke-WebRequest -UseBasicParsing http://localhost:5000/health

curl.exe http://localhost:5000/metrics
```

Expected:

```text
peoplepulse-mlflow ... Up ... (healthy)
StatusCode : 200
```

Then resume the complete stack:

```powershell
.\scripts\run_step8_mlops.ps1 -Scope synthetic_demo
```

# PeoplePulse AI STEP 9 — Local Ollama + LangGraph Analyst Agent

Merge this patch into the existing project root. Do not overwrite the real `.env` with `.env.example`.

## Install

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[activity,agent,dev]"
.\scripts\setup_step9_ollama.ps1
python scripts/check_step9_agent.py
pytest tests/test_step9_agent_policy.py -q
```

## Run

```powershell
.\scripts\run_step9_agent.ps1 -Scope aggregate
```

Dashboard:

```text
http://localhost:3000/#analyst
```

## Core privacy contract

Production uses only `aggregate` cohort analytics. The LLM has no arbitrary SQL tool and no tool that can fetch raw Slack messages, raw search text, or raw document names. Employee-level tools are synthetic-demo-only and require `demo-*` keys.

# PeoplePulse AI STEP 9.1 — Windows PowerShell UTF-8 JSON Fix

The FastAPI endpoint is valid. The smoke test failed before Ollama/LangGraph because
Windows PowerShell can encode a JSON string body using its default request encoding when
`charset` is not specified. The request contains Korean text, so FastAPI cannot parse the
resulting body as UTF-8 JSON.

This patch changes the smoke test to:

1. serialize JSON with `ConvertTo-Json -Compress`
2. convert the JSON explicitly to UTF-8 bytes
3. send `Content-Type: application/json; charset=utf-8`
4. print the server response body on HTTP errors

## Apply

Merge this patch into the project root, replacing:

```text
scripts/smoke_test_step9_agent.ps1
```

Then run:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/agent/health
.\scripts\smoke_test_step9_agent.ps1
```

If you want to test the endpoint manually:

```powershell
$payload = @{
    message = "최근 Slack 파생 신호를 요약해줘."
    scope = "aggregate"
    thread_id = "manual-test-001"
} | ConvertTo-Json -Compress

$utf8 = [System.Text.Encoding]::UTF8.GetBytes($payload)

Invoke-RestMethod `
    -Method POST `
    -Uri "http://localhost:8000/api/v1/agent/chat" `
    -ContentType "application/json; charset=utf-8" `
    -Body $utf8 `
    -TimeoutSec 120
```
