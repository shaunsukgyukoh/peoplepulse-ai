$ErrorActionPreference = "Continue"

Write-Host "PeoplePulse STEP 8.1 MLflow diagnostics"

Write-Host "`n==> Compose state"
docker compose --profile mlops ps -a

Write-Host "`n==> MLflow logs (last 250 lines)"
docker compose --profile mlops logs --tail=250 mlflow

Write-Host "`n==> PostgreSQL MLflow database check"
docker compose exec -T postgres psql `
  -U ${env:POSTGRES_USER} `
  -d ${env:POSTGRES_DB} `
  -c "SELECT datname FROM pg_database WHERE datname='peoplepulse_mlflow';"

Write-Host "`n==> MLflow container health metadata"
docker inspect peoplepulse-mlflow `
  --format '{{json .State.Health}}'

Write-Host "`n==> In-container /health probe (only works if container is running)"
docker compose --profile mlops exec -T mlflow python -c `
  "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5); print(r.status, r.read().decode())"

Write-Host "`n==> Host port probe"
try {
    $r = Invoke-WebRequest -UseBasicParsing http://localhost:5000/health -TimeoutSec 5
    Write-Host "host_health_status=$($r.StatusCode) body=$($r.Content)"
} catch {
    Write-Host "host_health_probe_failed=$($_.Exception.Message)"
}
