$legacy = @(
  "src/peoplepulse/activity/categorizer.py",
  "src/peoplepulse/activity/schema.py",
  "configs/activity_domain_policy.json",
  "scripts/upload_activity_excel.py",
  "tests/test_activity_categorizer.py",
  "scripts/apply_step4_migration.py",
  "data/synthetic/activity/monthly_activity_demo_2026-08.xlsx"
)
foreach ($path in $legacy) {
  if (Test-Path $path) {
    Remove-Item $path -Force
    Write-Host "Removed legacy STEP 4.0 file: $path"
  }
}
