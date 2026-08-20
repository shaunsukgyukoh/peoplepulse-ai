# PeoplePulse AI

**Privacy-Aware Employee Retention Intelligence Platform — portfolio project**

Current milestone: **STEP 5 — Identity Resolution + 7/30/90d Slack Rollups + ML-ready Feature Store**.

> Scope note: STEP 3 extracts message-level linguistic signals. It does not diagnose mental health and its outputs are not intended to automate hiring, firing, promotion, discipline, compensation, or other employment actions.


## STEP 5 — Canonical identity + feature fusion

STEP 5 adds a source-aware identity layer instead of fuzzy matching Slack IDs to names.

```text
Production-safe path
Slack User ID -> local explicit mapping -> HMAC department mapping
message_nlp_signal -> employee-first 7/30/90d rollups -> department aggregation
+ department_monthly_activity -> department_monthly_fusion

Synthetic portfolio path
Slack demo ID -> canonical demo employee <- synthetic activity-report name
-> HMAC-only synthetic identity map
-> employee 7/30/90d Slack features + monthly activity features
-> synthetic_employee_retention_feature
```

Important design boundary: **employee-level fused features are generated only for synthetic portfolio data**. The production path persists cohort/department features only and suppresses cohorts below the configured minimum size. Raw names, Slack IDs, search text, document names, and browsing details are not written to the STEP 5 feature tables.

Runbook: `docs/step5-runbook.md`. Architecture: `docs/architecture-step5.md`.

## Architecture so far

```text
Slack work channels
  -> Events API / Socket Mode
  -> Slack Bolt listener
  -> PII redaction + HMAC pseudonymization
  -> ephemeral Redis Stream: peoplepulse:slack-events
  -> Redis Consumer Group: peoplepulse:nlp-workers
  -> local NLP worker (baseline or Hugging Face/PyTorch)
  -> PostgreSQL features.message_nlp_signal (scores only; no message text)
  -> Redis Stream: peoplepulse:nlp-results (derived scores only)
  -> XACK + XDEL transient Slack queue entry
```

The worker periodically uses stale-pending recovery so an event handed to a crashed worker can be reclaimed and processed by a healthy worker. PostgreSQL uses `event_id` as the primary key so retry processing is idempotent.

## STEP 3 label set

This is a **multi-label** message classification problem:

- `satisfied`
- `neutral`
- `frustrated`
- `angry`
- `dissatisfied`
- `overloaded`
- `conflict`
- `disengaged`

`disengaged` means linguistic signals of low work engagement/distancing, not depression or another health diagnosis. `neutral` is a fallback label and is suppressed at runtime when a non-neutral score crosses the configured threshold.

## Model experiment ladder

| Candidate | Role | Why it is in the experiment |
|---|---|---|
| TF-IDF + Logistic Regression | Baseline | very fast, explainable, char n-grams tolerate spacing/typos |
| `beomi/KcELECTRA-small-v2022` | Transformer | local real-time efficiency candidate |
| `beomi/KcELECTRA-base` | Transformer | noisy/conversational Korean accuracy candidate |
| `klue/roberta-base` | Transformer | general Korean NLU reference candidate |

Primary metric: **Macro-F1**. Also record Micro-F1, macro precision/recall, per-label F1, subset accuracy, Hamming loss, and mean/p95 single-message inference latency.

The included `data/synthetic/nlp/workplace_messages_v01.csv` is a synthetic portfolio dataset for pipeline validation. Its scores must not be presented as real-employee model performance. A production study needs governed, anonymized/consented, human-labeled data and leakage-safe splits.

## 1. Apply the STEP 3 database migration

Existing PostgreSQL volumes do not automatically rerun Docker init scripts. With PostgreSQL already running:

```powershell
docker compose up -d
Get-Content -Raw infra/postgres/migrations/002_step3_nlp.sql | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

The durable table is:

```text
features.message_nlp_signal
```

It stores pseudonymous IDs, timestamps, model metadata, latency, and eight scores — **not Slack message text**.

## 2. Install local ML dependencies (Windows + NVIDIA CUDA)

The local training machine initially installed a CPU-only PyTorch build, so CUDA was not detected.
For this project, the verified recovery path is to install the CUDA 12.1 PyTorch wheel explicitly **before** the remaining NLP dependencies:

```powershell
python -m pip uninstall -y torch torchvision torchaudio
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[nlp,dev]"
```

`torch` is intentionally not included in the `nlp` optional dependency anymore, so the final `pip install -e` command does not replace the CUDA wheel with another PyTorch build.

Verify the active environment:

```powershell
python -c "import torch; print('torch=', torch.__version__); print('torch cuda=', torch.version.cuda); print('available=', torch.cuda.is_available()); print('gpu=', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

The project Docker NLP image remains CPU-first for portability. GPU-enabled Docker runtime is intentionally deferred; local Windows/NVIDIA experiments use the CUDA-enabled virtual environment above.

## 3. Reproduce the synthetic evaluation dataset

The CSV is already included. To regenerate it deterministically:

```powershell
python scripts/generate_nlp_dataset.py
```

Current v0.1 dataset size: 276 synthetic messages with train/validation/test splits and multi-label examples.

## 4. Train the lexical baseline

```powershell
python scripts/train_baseline.py
```

Outputs:

```text
artifacts/models/tfidf-logreg/model.joblib
artifacts/models/tfidf-logreg/metrics.json
```

This gives the minimum bar every Transformer must beat on Macro-F1 while showing the latency trade-off.

## 5. Fine-tune Transformer candidates

Start with the real-time candidate:

```powershell
python scripts/train_transformer.py --model-name beomi/KcELECTRA-small-v2022
```

Then the higher-capacity conversational candidate:

```powershell
python scripts/train_transformer.py --model-name beomi/KcELECTRA-base
```

Then the general Korean NLU reference:

```powershell
python scripts/train_transformer.py --model-name klue/roberta-base
```

Each run writes a Hugging Face-compatible checkpoint and `metrics.json` under `artifacts/models/<model-name>/`.

Useful options:

```powershell
python scripts/train_transformer.py `
  --model-name beomi/KcELECTRA-small-v2022 `
  --epochs 3 `
  --batch-size 16 `
  --max-length 128 `
  --device auto
```

`--device auto` selects CUDA when available, then Apple MPS, otherwise CPU.

## 6. Calibrate thresholds and re-benchmark checkpoints

The first experiment used a global threshold of `0.5`. Because the first Transformer runs showed very high recall but much lower precision, STEP 3.1 tunes one threshold per label on the **validation split only**, freezes those thresholds, and evaluates them once on the test split.

The evaluator also synchronizes CUDA before wall-clock timing ends, fixing the original asynchronous-GPU latency benchmark. Existing checkpoints can be reused; retraining is not required just for this step.

Baseline:

```powershell
python scripts/evaluate_baseline_checkpoint.py
```

Transformer checkpoints:

```powershell
python scripts/evaluate_transformer_checkpoint.py `
  --model-dir artifacts/models/klue__roberta-base `
  --device cuda

python scripts/evaluate_transformer_checkpoint.py `
  --model-dir artifacts/models/beomi__KcELECTRA-base `
  --device cuda

python scripts/evaluate_transformer_checkpoint.py `
  --model-dir artifacts/models/beomi__KcELECTRA-small-v2022 `
  --device cuda
```

Each model directory receives:

```text
thresholds.json
metrics_tuned.json
```

The test split is never used to choose thresholds.

## 7. Compare Macro-F1 and synchronized latency

```powershell
python scripts/compare_nlp_models.py
```

The comparison script automatically prefers `metrics_tuned.json` when it exists and otherwise falls back to the original `metrics.json`. Outputs:

```text
artifacts/reports/nlp_model_comparison.csv
artifacts/reports/nlp_model_comparison.json
```

Current first-run accuracy leader is `klue/roberta-base` (Macro-F1 0.6764 at the original 0.5 threshold), but final selection must use the calibrated evaluation and synchronized p95 latency. See `docs/experiment-log-step3.md`.

## 8. Select the Transformer checkpoint used by the real-time worker

Example:

```powershell
python scripts/select_nlp_model.py --source artifacts/models/beomi__KcELECTRA-small-v2022
```

This creates:

```text
artifacts/models/selected/
```

The Docker worker mounts that directory at `/models/selected`.

## 9. Add STEP 3 values to `.env`

```env
NLP_CONSUMER_GROUP=peoplepulse:nlp-workers
NLP_BATCH_SIZE=8
NLP_BLOCK_MS=5000
NLP_PENDING_MIN_IDLE_MS=60000
NLP_RECOVERY_INTERVAL_SECONDS=30
REDIS_STREAM_NLP_MAXLEN=50000

NLP_BACKEND=transformer
NLP_MODEL_PATH=/models/selected
NLP_BASELINE_MODEL_PATH=/models/tfidf-logreg/model.joblib
NLP_THRESHOLD=0.5
NLP_DEVICE=auto
```

For a quick end-to-end pipeline smoke test before Transformer training, set:

```env
NLP_BACKEND=baseline
```

and train the baseline first.

## 10. Start Slack + NLP runtime

Baseline or selected Transformer model must exist before the NLP worker starts.

```powershell
docker compose --profile slack --profile nlp up -d --build
```

Check:

```powershell
docker compose --profile slack --profile nlp ps
docker compose logs -f nlp-worker
```

Expected worker log:

```text
NLP worker started backend=transformer group=peoplepulse:nlp-workers consumer=...
```

Send a human-authored message in an authorized Slack test channel. After successful inference, the worker logs only event/model/latency metadata, not message text.

## 11. Verify derived results

Redis input queue should be consumed/deleted after successful processing:

```powershell
docker compose exec redis redis-cli XLEN peoplepulse:slack-events
```

Derived-score stream grows:

```powershell
docker compose exec redis redis-cli XLEN peoplepulse:nlp-results
```

Check PostgreSQL aggregate without exposing employee message text:

```powershell
python scripts/check_nlp_results.py
```

## Tests

```powershell
pytest -q
ruff check .
```

## STEP 3 portfolio talking points

- Why multi-label classification is more appropriate than simple positive/negative sentiment for workplace messages.
- Why Macro-F1 is the primary model-selection metric.
- Why both char n-gram lexical baseline and Korean pretrained Transformers are evaluated.
- Why real-time model selection includes p95 latency, not accuracy alone.
- How Redis Consumer Groups provide horizontal work distribution and pending-entry recovery.
- How PII masking, pseudonymous identifiers, transient Redis storage, and derived-only PostgreSQL persistence reduce privacy exposure.
- Why synthetic evaluation results are pipeline evidence, not proof of production accuracy.


## STEP 3.2 — promote the measured model and verify real-time CUDA inference

After STEP 3.1 comparison, promote the best model under the portfolio gate (`Macro-F1 >= 0.70`, `P95 <= 20 ms`):

```powershell
python scripts/promote_nlp_model.py
```

Apply the runtime-threshold migration:

```powershell
Get-Content -Raw infra/postgres/migrations/003_step3_runtime_thresholds.sql |
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

For the current Windows/NVIDIA development environment, keep PostgreSQL and Redis in Docker and run the NLP worker from the CUDA-enabled host virtualenv:

```powershell
docker compose up -d postgres redis
.\scripts\run_nlp_worker_local.ps1
```

In a second PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/smoke_test_realtime_nlp.py
```

The smoke test inserts only a synthetic workplace sentence, then verifies Redis -> CUDA Transformer -> PostgreSQL without requiring a real employee Slack message. After that passes, start the Slack listener and test `#peoplepulse-test`.

> The `nlp-worker` Docker image remains CPU-portable in STEP 3.2. Host CUDA is the verified GPU path. GPU Docker packaging is deferred to the container/MLOps phase so a working Windows CUDA environment is not replaced by an unverified container GPU stack.


### Redis blocking-read timeout note (STEP 3.2.1)

redis-py 8.x uses a finite socket read timeout by default. Because the NLP worker uses
`XREADGROUP BLOCK`, the client socket timeout must be longer than the Redis blocking window.
The worker therefore uses `NLP_REDIS_SOCKET_TIMEOUT_SECONDS=15` with
`NLP_BLOCK_MS=5000`, and transient Redis read timeouts are retried rather than terminating
the process.


## STEP 4 — Actual 3-report month-end ingestion

STEP 4 now matches the three real exports used by the project instead of the earlier generic `Employee / Date Time / URL / Duration` workbook.

Expected report set (order does not matter):

1. `취업사이트 접속내역*.xls|xlsx`
   - `이름 / 부서 / 총 접속 시간 / 접속 사이트 / 타이틀 / 접속 시간 ↓ / 접속일`
2. `웹 검색 내역*.xls|xlsx`
   - `이름 / 부서 / 검색 키워드 ↓ / 키워드 / 검색어 / 검색 사이트 / 검색일`
3. `문서활용 내역*.xls|xlsx`
   - `이름 / 부서 / 활용 키워드 ↓ / 키워드 / 문서명 / 구분 / 시각`

The parser does **not** trust filenames. It reads the workbook with `python-calamine`, scans the header signature, detects the report type, forward-fills employee/department values used by the export format, normalizes department labels, validates each normalized frame with Pandera, filters sensitive content in memory, and writes only derived monthly features plus audit counts.

### Privacy modes

`ACTIVITY_PRIVACY_MODE=aggregate` is the default for real reports:

- employee names, search text, titles, document names and sites are not stored;
- department identifiers are HMAC-pseudonymized;
- departments below `ACTIVITY_MIN_COHORT_SIZE` are suppressed;
- sensitive rows are omitted and retained only as batch-level category counts;
- no employee-level attrition feature is produced from real browsing/search/document activity.

`ACTIVITY_PRIVACY_MODE=synthetic_demo` is reserved for portfolio data. Runtime code requires **all three filenames** to start with `Synthetic_` before an employee-level feature can be written to `features.synthetic_employee_monthly_activity`.

### Install / migrate / run

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[activity,dev]"

docker compose up -d postgres redis
python scripts/apply_step4_actual_reports_migration.py

docker compose --profile activity up -d --build --force-recreate api
```

Open:

```text
http://localhost:8000/admin/activity-upload
```

The page requires all three `.xls/.xlsx` files in one request. The order is irrelevant because report type detection is based on headers.

### Synthetic actual-format smoke test

For portfolio testing set:

```env
ACTIVITY_PRIVACY_MODE=synthetic_demo
ACTIVITY_MIN_COHORT_SIZE=5
ACTIVITY_DEMO_FILENAME_PREFIX=Synthetic_
ACTIVITY_CONTENT_POLICY_PATH=configs/activity_content_policy.json
```

Then upload the three files under:

```text
data/synthetic/activity/actual-format/
```

or use:

```powershell
python scripts/upload_activity_report_set.py --month 2026-07 `
  "data/synthetic/activity/actual-format/Synthetic_취업사이트 접속내역2026-07-01~2026-07-31.xlsx" `
  "data/synthetic/activity/actual-format/Synthetic_웹 검색 내역2026-07-01~2026-07-31.xlsx" `
  "data/synthetic/activity/actual-format/Synthetic_문서활용 내역2026-07-01~2026-07-31.xlsx"
```

Verify:

```powershell
python scripts/check_activity_features.py
```

### PostgreSQL

Production-safe table:

```text
features.department_monthly_activity
```

Synthetic-only employee table:

```text
features.synthetic_employee_monthly_activity
```

Audit tables:

```text
audit.activity_report_set_batch
audit.activity_report_file
audit.activity_report_exclusion_summary
```

Raw workbook bytes, names, search text, titles, document names and sites are never written to these tables.


## STEP 6 — Synthetic attrition ML experiment

STEP 6 is intentionally **synthetic-demo only** for employee-level modeling. It generates a multi-month
synthetic panel, engineers 30/60/90-day future attrition labels, applies a 3-month purged temporal split,
and compares Logistic Regression, XGBoost, LightGBM and CatBoost. The primary ranking metric is Average
Precision / PR-AUC, with Recall@Top-K, Brier score and calibration error reported alongside ROC-AUC.

Two feature sets are evaluated:

- `privacy_safe` — default; excludes direct job-search/search-activity intent proxies;
- `synthetic_full` — synthetic-only ablation used to quantify the incremental predictive value of those
  intrusive proxies without recommending them for real deployment.

Install and run:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[ml,dev]"
.\scripts\run_step6_experiment.ps1
```

See `docs/step6-runbook.md`, `docs/architecture-step6.md`, and `docs/model-card-step6.md`.

## STEP 7 — PeoplePulse Product Dashboard

STEP 7 adds the portfolio UI over the existing pipelines:

- Next.js 16.3.1 + React 19.2 + TypeScript
- Tailwind CSS 4.3 + Apache ECharts 6
- Executive Overview
- FastAPI Server-Sent Events for real-time derived Slack signals
- three-file monthly report upload
- synthetic retention model evaluation and intent-proxy ablation
- SHAP global feature importance
- NLP benchmark / latency view

Start it with:

```powershell
.\scripts\run_step7_dashboard.ps1
```

Then open `http://localhost:3000`. Employee-level attrition content remains synthetic-demo-only; production-facing analytics remain department/cohort scoped.


## STEP 8 — MLOps / Model & Data Drift Monitoring

STEP 8 adds a fully self-hosted observability stack:

- MLflow 3.15.1 tracking server with PostgreSQL metadata and a Docker artifact volume;
- Evidently 0.7.21 batch data-drift reports;
- Prometheus 3.13.2 LTS scraping FastAPI and MLflow metrics;
- Grafana 13.1 provisioned dashboards;
- recurring monitoring worker and Prometheus alert rules.

Run:

```powershell
.\scripts\run_step8_mlops.ps1 -Scope synthetic_demo
```

Use `-Scope aggregate` for production-safe cohort drift. Employee-level model monitoring remains synthetic-demo-only. See `docs/step8-runbook.md`.
