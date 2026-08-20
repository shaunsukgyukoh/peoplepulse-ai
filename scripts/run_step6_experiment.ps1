$ErrorActionPreference = "Stop"

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host "`n==> $Name"
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Write-Host "PeoplePulse STEP 6 synthetic attrition experiment"

# PowerShell's ErrorActionPreference does not reliably convert native-process
# non-zero exit codes into terminating errors on every Windows PowerShell version.
# Explicitly check $LASTEXITCODE after every Python step.
Invoke-PythonStep -Name "Dependency preflight" -Arguments @("scripts/check_step6_dependencies.py")
Invoke-PythonStep -Name "Generate synthetic attrition panel" -Arguments @("scripts/generate_step6_synthetic_panel.py")
Invoke-PythonStep -Name "Train and evaluate candidate models" -Arguments @("scripts/train_step6_models.py")
Invoke-PythonStep -Name "Validate STEP 6 experiment artifacts" -Arguments @("scripts/check_step6_results.py")
Invoke-PythonStep -Name "Generate SHAP explanation artifacts" -Arguments @(
    "scripts/explain_step6_model.py",
    "--experiment-dir",
    "artifacts/ml/step6/privacy_safe"
)

Write-Host "`n[OK] STEP 6 experiment complete"
