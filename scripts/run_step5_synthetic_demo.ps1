$ErrorActionPreference = "Stop"

Write-Host "PeoplePulse STEP 5 synthetic feature-store demo"

$env:APP_ENV = "development"
$env:ACTIVITY_PRIVACY_MODE = "synthetic_demo"

python scripts/apply_step5_migration.py
python scripts/load_identity_map.py --mode synthetic_demo --path "data/synthetic/identity/canonical_employee_map.csv"
python scripts/seed_step5_synthetic_slack.py
python scripts/build_step5_features.py --month 2026-07 --mode synthetic_demo
python scripts/check_step5_features.py --month 2026-07 --mode synthetic_demo
