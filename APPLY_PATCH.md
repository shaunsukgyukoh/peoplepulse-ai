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
