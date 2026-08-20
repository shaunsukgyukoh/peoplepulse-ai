# STEP 4 Runbook — Actual 3 Report Set

## 1. Install

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[activity,dev]"
```

This does not reinstall the manually verified CUDA PyTorch wheel.

## 2. `.env`

Production-safe defaults:

```env
ACTIVITY_ADMIN_TOKEN=<random-secret>
ACTIVITY_CONTENT_POLICY_PATH=configs/activity_content_policy.json
ACTIVITY_PRIVACY_MODE=aggregate
ACTIVITY_MIN_COHORT_SIZE=5
ACTIVITY_DEMO_FILENAME_PREFIX=Synthetic_
ACTIVITY_MAX_UPLOAD_BYTES=20971520
ACTIVITY_WORKDAY_START_HOUR=9
ACTIVITY_WORKDAY_END_HOUR=18
```

For the included synthetic employee-level test only:

```env
ACTIVITY_PRIVACY_MODE=synthetic_demo
```

Do not use `synthetic_demo` for actual employee reports.

## 3. Migration

```powershell
docker compose up -d postgres redis
python scripts/apply_step4_actual_reports_migration.py
```

## 4. API

```powershell
docker compose --profile activity up -d --build --force-recreate api
docker compose --profile activity ps
```

`peoplepulse-api` should expose:

```text
0.0.0.0:8000->8000/tcp
```

Health:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Upload UI:

```text
http://localhost:8000/admin/activity-upload
```

## 5. Synthetic actual-format test

Use all 3 files under:

```text
data/synthetic/activity/actual-format/
```

Report month:

```text
2026-07
```

The three file controls can be filled in any order. The backend validates that the request contains exactly one header signature for each report type.

## 6. CLI alternative

```powershell
python scripts/upload_activity_report_set.py --month 2026-07 `
  "data/synthetic/activity/actual-format/Synthetic_취업사이트 접속내역2026-07-01~2026-07-31.xlsx" `
  "data/synthetic/activity/actual-format/Synthetic_웹 검색 내역2026-07-01~2026-07-31.xlsx" `
  "data/synthetic/activity/actual-format/Synthetic_문서활용 내역2026-07-01~2026-07-31.xlsx"
```

## 7. Verify

```powershell
python scripts/check_activity_features.py
```

Synthetic mode:

```powershell
docker compose exec postgres psql -U peoplepulse -d peoplepulse -c "SELECT report_month, COUNT(*) FROM features.synthetic_employee_monthly_activity GROUP BY report_month;"
```

Production aggregate mode:

```powershell
docker compose exec postgres psql -U peoplepulse -d peoplepulse -c "SELECT report_month, COUNT(*) FROM features.department_monthly_activity GROUP BY report_month;"
```

The feature tables intentionally have no raw name/search/title/document/site columns.
