$ErrorActionPreference = "Stop"

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "Build MLflow image" {
    docker compose --profile mlops build --no-cache mlflow
}

Invoke-Step "Verify exporter import inside image" {
    docker compose --profile mlops run --rm --no-deps --entrypoint python mlflow `
        -c "import mlflow, prometheus_flask_exporter; print('mlflow=' + mlflow.__version__); print('prometheus_flask_exporter=OK')"
}

Write-Host "`n[OK] MLflow image contains Prometheus exporter dependency." -ForegroundColor Green
