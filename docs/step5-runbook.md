# STEP 5 Runbook

## Apply migration

```powershell
docker compose up -d postgres redis
python scripts/apply_step5_migration.py
```

## Synthetic portfolio path

Prerequisites:

1. STEP 4 synthetic 3-report upload for `2026-07` has populated
   `features.synthetic_employee_monthly_activity`.
2. `APP_ENV=development`.
3. The same `EMPLOYEE_HASH_KEY` from Slack/STEP 4 is still in use.

Run:

```powershell
python scripts/load_identity_map.py `
  --mode synthetic_demo `
  --path "data/synthetic/identity/canonical_employee_map.csv"

python scripts/seed_step5_synthetic_slack.py
python scripts/build_step5_features.py --month 2026-07 --mode synthetic_demo
python scripts/check_step5_features.py --month 2026-07 --mode synthetic_demo
```

Or:

```powershell
.\scripts\run_step5_synthetic_demo.ps1
```

## Production-safe department path

Create a local CSV that is **not committed to Git**:

```csv
slack_user_id,department
U01234567,연구개발본부
U07654321,연구개발본부
```

Then load only its HMAC mapping:

```powershell
python scripts/load_identity_map.py --mode aggregate --path "C:\secure\slack_department_map.csv"
python scripts/build_step5_features.py --month 2026-07 --mode aggregate
python scripts/check_step5_features.py --month 2026-07 --mode aggregate
```

The mapping table stores hashes only; raw Slack IDs and department strings are not persisted by the
loader. Departments without the configured minimum Slack cohort are omitted from the Slack/fused
feature mart.

## Export the ML-ready matrix

```powershell
python scripts/export_step5_feature_matrix.py --month 2026-07 --mode synthetic_demo
```

Outputs under `artifacts/features/` include a CSV plus a JSON manifest. HMAC identifiers are listed
as traceability columns and are explicitly excluded from `model_feature_columns`. STEP 5 does not
create an attrition target; target construction and leakage controls belong to STEP 6.
