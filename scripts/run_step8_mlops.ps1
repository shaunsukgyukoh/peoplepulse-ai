param(
    [ValidateSet("synthetic_demo", "aggregate")]
    [string]$Scope = "synthetic_demo"
)

$ErrorActionPreference = "Stop"

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "`n==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Write-Host "PeoplePulse STEP 8 MLOps stack scope=$Scope"
$env:MLOPS_MONITORING_SCOPE = $Scope

Invoke-NativeStep -Name "STEP 8 static preflight" -Command {
    python scripts/check_step8_mlops.py
}

Write-Host "`n==> Build and start MLOps infrastructure"
docker compose --profile mlops up -d --build --force-recreate postgres api mlflow prometheus grafana
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] MLOps infrastructure did not become healthy."
    Write-Host "[INFO] Printing MLflow diagnostics before stopping..."
    docker compose --profile mlops ps -a
    docker compose --profile mlops logs --tail=250 mlflow
    throw "Build and start MLOps infrastructure failed with exit code $LASTEXITCODE"
}

Invoke-NativeStep -Name "Import existing STEP 3/6 experiment history into MLflow" -Command {
    docker compose --profile mlops run --rm -e MLOPS_MONITORING_SCOPE=$Scope monitoring-worker `
        python scripts/log_step8_history_to_mlflow.py
}

Invoke-NativeStep -Name "Generate initial Evidently monitoring snapshot" -Command {
    docker compose --profile mlops run --rm -e MLOPS_MONITORING_SCOPE=$Scope monitoring-worker `
        python scripts/run_step8_drift.py --scope $Scope
}

Invoke-NativeStep -Name "Start recurring monitoring worker" -Command {
    docker compose --profile mlops up -d monitoring-worker
}

Invoke-NativeStep -Name "Show MLOps services" -Command {
    docker compose --profile mlops ps
}

Write-Host "`n[OK] MLflow:     http://localhost:5000"
Write-Host "[OK] Prometheus: http://localhost:9090"
Write-Host "[OK] Grafana:    http://localhost:3001"
Write-Host "[OK] API metrics:http://localhost:8000/metrics"
Write-Host "[OK] Drift API:  http://localhost:8000/api/v1/monitoring/summary"
